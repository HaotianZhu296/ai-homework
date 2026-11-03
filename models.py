"""Database tables."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on the way back out; treat stored values as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    moods: Mapped[list[Mood]] = relationship(back_populates="user", cascade="all, delete-orphan")
    favorites: Mapped[list[Favorite]] = relationship(back_populates="user", cascade="all, delete-orphan")


class AuthSession(Base):
    """A logged-in browser. Only a SHA-256 hash of the cookie token is stored."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remember: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped[User] = relationship()


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


class Mood(Base):
    """A user-defined mood that maps onto a built-in mood, optionally with a focus filter."""

    __tablename__ = "moods"
    __table_args__ = (UniqueConstraint("user_id", "label_key", name="uq_mood_user_label"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(40))
    label_key: Mapped[str] = mapped_column(String(40))  # lower-cased label, for uniqueness
    base_mood: Mapped[str] = mapped_column(String(32))
    focus_type: Mapped[str | None] = mapped_column(String(1), nullable=True)  # "c" category / "a" area
    focus_value: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="moods")

    @property
    def key(self) -> str:
        return f"custom-{self.id}"


class Favorite(Base):
    """A recipe saved by a user, with a snapshot of the recipe at save time."""

    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "meal_id", name="uq_favorite_user_meal"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    meal_id: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    area: Mapped[str | None] = mapped_column(String(60), nullable=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    youtube: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingredients: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="favorites")
    moods: Mapped[list[FavoriteMood]] = relationship(
        back_populates="favorite", cascade="all, delete-orphan", order_by="FavoriteMood.saved_at"
    )


class FavoriteMood(Base):
    """A mood a favorite was saved under. The label is copied so it survives mood deletion."""

    __tablename__ = "favorite_moods"
    __table_args__ = (UniqueConstraint("favorite_id", "mood_key", name="uq_favorite_mood"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    favorite_id: Mapped[int] = mapped_column(ForeignKey("favorites.id", ondelete="CASCADE"), index=True)
    mood_key: Mapped[str] = mapped_column(String(40))
    mood_label: Mapped[str] = mapped_column(String(40))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    favorite: Mapped[Favorite] = relationship(back_populates="moods")
