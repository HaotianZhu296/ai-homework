"""Register / login / logout / forgot + reset password, and the current-user dependency."""

from __future__ import annotations

import logging
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from config import settings
from db import get_db
from models import AuthSession, PasswordResetToken, User, as_utc, utcnow
from security import DUMMY_HASH, MAX_PASSWORD_BYTES, hash_password, hash_token, new_token, verify_password

log = logging.getLogger("mood_recipes.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])

MIN_PASSWORD_LENGTH = 8


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes.")
    return value


class Credentials(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class RegisterIn(Credentials):
    @field_validator("password")
    @classmethod
    def _strong_enough(cls, value: str) -> str:
        return _check_password(value)


class LoginIn(Credentials):
    remember: bool = False


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, value: str) -> str:
        return _check_password(value)


class TokenIn(BaseModel):
    token: str


def user_payload(user: User) -> dict:
    return {"id": user.id, "email": user.email}


# ---- sessions --------------------------------------------------------------------------

def _start_session(db: Session, response: Response, user: User, remember: bool) -> None:
    token = new_token()
    lifetime = timedelta(days=settings.remember_days) if remember else timedelta(hours=settings.session_hours)
    db.add(AuthSession(token_hash=hash_token(token), user_id=user.id, expires_at=utcnow() + lifetime, remember=remember))
    db.commit()
    response.set_cookie(
        settings.session_cookie,
        token,
        # Without max_age the cookie is dropped when the browser closes.
        max_age=int(lifetime.total_seconds()) if remember else None,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def _session_for(request: Request, db: Session) -> AuthSession | None:
    token = request.cookies.get(settings.session_cookie)
    if not token:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None:
        return None
    if as_utc(session.expires_at) <= utcnow():
        db.delete(session)
        db.commit()
        return None
    return session


def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    session = _session_for(request, db)
    return session.user if session else None


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first.")
    return user


# ---- email -----------------------------------------------------------------------------

def _send_reset_email(to: str, link: str) -> None:
    if not settings.smtp_host:
        log.warning("SMTP not configured; password reset link for %s: %s", to, link)
        return
    msg = EmailMessage()
    msg["Subject"] = "Reset your Mood Recipes password"
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Someone asked to reset the password for {to}.\n\n"
        f"Open this link within {settings.reset_minutes} minutes to choose a new password:\n{link}\n\n"
        "If this wasn't you, you can ignore this email."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        log.exception("Could not send password reset email to %s", to)


# ---- routes ----------------------------------------------------------------------------

@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    _start_session(db, response, user, remember=False)
    return {"user": user_payload(user)}


@router.post("/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        verify_password(body.password, DUMMY_HASH)  # same cost as a real check
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    now = utcnow()
    if user.locked_until and as_utc(user.locked_until) > now:
        minutes = max(1, int((as_utc(user.locked_until) - now).total_seconds() // 60) + 1)
        raise HTTPException(status_code=429, detail=f"Too many failed attempts. Try again in {minutes} min.")

    if not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= settings.max_failed_logins:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_logins = 0
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user.failed_logins = 0
    user.locked_until = None
    db.commit()
    _start_session(db, response, user, remember=body.remember)
    return {"user": user_payload(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    session = _session_for(request, db)
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User | None = Depends(current_user)):
    return {"user": user_payload(user) if user else None}


@router.post("/forgot")
def forgot_password(body: ForgotIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    message = "If an account exists for that email, a reset link has been sent."
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None:
        return {"message": message}

    # Only the newest link should work.
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token = new_token()
    db.add(PasswordResetToken(
        token_hash=hash_token(token),
        user_id=user.id,
        expires_at=utcnow() + timedelta(minutes=settings.reset_minutes),
    ))
    db.commit()

    link = f"{settings.base_url.rstrip('/')}/reset-password.html?token={token}"
    tasks.add_task(_send_reset_email, user.email, link)
    result = {"message": message}
    if settings.dev_show_reset_link and not settings.smtp_host:
        result["dev_reset_link"] = link
    return result


def _valid_reset_token(db: Session, token: str) -> PasswordResetToken | None:
    record = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if record is None or record.used_at is not None or as_utc(record.expires_at) <= utcnow():
        return None
    return record


@router.post("/reset/check")
def check_reset_token(body: TokenIn, db: Session = Depends(get_db)):
    record = _valid_reset_token(db, body.token)
    return {"valid": record is not None, "email": record.user.email if record else None}


@router.post("/reset")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    record = _valid_reset_token(db, body.token)
    if record is None:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")
    user = record.user
    user.password_hash = hash_password(body.password)
    user.failed_logins = 0
    user.locked_until = None
    record.used_at = utcnow()
    # Sign out everywhere so a stolen session can't outlive the password change.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.commit()
    return {"ok": True, "email": user.email}
