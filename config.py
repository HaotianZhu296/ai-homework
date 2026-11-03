"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'mood_recipes.db'}")
    )
    # Public URL used to build password-reset links.
    base_url: str = field(default_factory=lambda: os.getenv("BASE_URL", "http://localhost:8000"))
    # Set COOKIE_SECURE=1 when serving over HTTPS.
    cookie_secure: bool = field(default_factory=lambda: _flag("COOKIE_SECURE", False))
    # Without SMTP there is no way to deliver reset emails locally, so by default the
    # reset link is returned to the browser. Turn this off in production.
    dev_show_reset_link: bool = field(default_factory=lambda: _flag("DEV_SHOW_RESET_LINK", True))
    smtp_host: str | None = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str | None = field(default_factory=lambda: os.getenv("SMTP_USER"))
    smtp_password: str | None = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", "Mood Recipes <no-reply@localhost>"))

    session_cookie: str = "mr_session"
    remember_days: int = 30
    session_hours: int = 12
    reset_minutes: int = 30
    max_failed_logins: int = 5
    lockout_minutes: int = 15


settings = Settings()
