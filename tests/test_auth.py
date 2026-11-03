from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from config import settings
from models import AuthSession, PasswordResetToken, User, utcnow
from tests.conftest import register


def test_register_hashes_password_and_logs_in(client):
    r = register(client, "Alice@Example.com")
    assert r.json()["user"]["email"] == "alice@example.com"
    assert settings.session_cookie in r.cookies

    with client.Session() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$2b$")
        assert "correct horse" not in user.password_hash
        session = db.scalar(select(AuthSession))
        # Only the hash of the cookie token is stored.
        assert session.token_hash != r.cookies[settings.session_cookie]

    assert client.get("/api/auth/me").json()["user"]["email"] == "alice@example.com"


def test_register_validation(client):
    assert client.post("/api/auth/register", json={"email": "nope", "password": "longenough"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "a@example.com", "password": "short"}).status_code == 422
    register(client, "a@example.com")
    dup = client.post("/api/auth/register", json={"email": "A@example.com", "password": "another one"})
    assert dup.status_code == 409


def test_login_logout(client):
    register(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["user"] is None

    bad = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong password"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "whatever"})
    assert unknown.status_code == 401
    assert bad.json()["detail"] == unknown.json()["detail"]  # no account enumeration

    ok = client.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "correct horse"})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["email"] == "alice@example.com"

    client.post("/api/auth/logout")
    with client.Session() as db:
        assert db.scalar(select(AuthSession)) is None  # revoked server-side


def test_remember_me_sets_persistent_cookie(client):
    register(client)
    plain = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse"})
    assert "max-age" not in plain.headers["set-cookie"].lower()
    remembered = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "correct horse", "remember": True}
    )
    cookie = remembered.headers["set-cookie"].lower()
    assert f"max-age={settings.remember_days * 86400}" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_expired_session_is_rejected(client):
    register(client)
    with client.Session() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me").json()["user"] is None


def test_lockout_after_repeated_failures(client):
    register(client)
    client.post("/api/auth/logout")
    for _ in range(settings.max_failed_logins):
        client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong password"})
    locked = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse"})
    assert locked.status_code == 429


def _reset_token(client, email="alice@example.com"):
    r = client.post("/api/auth/forgot", json={"email": email})
    assert r.status_code == 200
    link = r.json()["dev_reset_link"]
    return parse_qs(urlparse(link).query)["token"][0]


def test_forgot_password_does_not_reveal_accounts(client):
    r = client.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "dev_reset_link" not in r.json()


def test_reset_password_flow(client):
    register(client)
    token = _reset_token(client)
    with client.Session() as db:
        stored = db.scalar(select(PasswordResetToken))
        assert stored.token_hash != token

    check = client.post("/api/auth/reset/check", json={"token": token}).json()
    assert check == {"valid": True, "email": "alice@example.com"}

    assert client.post("/api/auth/reset", json={"token": token, "password": "short"}).status_code == 422
    r = client.post("/api/auth/reset", json={"token": token, "password": "brand new pass"})
    assert r.status_code == 200

    # Existing sessions are revoked, the old password stops working, the token is single-use.
    assert client.get("/api/auth/me").json()["user"] is None
    old = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse"})
    assert old.status_code == 401
    new = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "brand new pass"})
    assert new.status_code == 200
    again = client.post("/api/auth/reset", json={"token": token, "password": "another pass"})
    assert again.status_code == 400


def test_only_newest_reset_link_works_and_links_expire(client):
    register(client)
    first = _reset_token(client)
    second = _reset_token(client)
    assert client.post("/api/auth/reset/check", json={"token": first}).json()["valid"] is False
    assert client.post("/api/auth/reset/check", json={"token": second}).json()["valid"] is True

    with client.Session() as db:
        record = db.scalar(select(PasswordResetToken))
        record.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.post("/api/auth/reset", json={"token": second, "password": "brand new pass"}).status_code == 400
    assert client.post("/api/auth/reset/check", json={"token": "garbage"}).json()["valid"] is False
