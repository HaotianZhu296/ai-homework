"""Built-in + user-defined moods, and resolving a mood key to recipe filters."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import current_user, require_user
from db import get_db
from models import Mood, User
from recipe_service import AREAS, CATEGORIES, MOOD_LABELS, VALID_MOODS, filters_for

router = APIRouter(prefix="/api/moods", tags=["moods"])

MAX_CUSTOM_MOODS = 30
FOCUS_TYPES = {"c": CATEGORIES, "a": AREAS}


@dataclass(frozen=True)
class ResolvedMood:
    key: str
    label: str
    filter_groups: list[list[tuple[str, str]]]


def builtin_payload() -> list[dict]:
    return [{"key": slug, "label": label, "custom": False} for slug, label in MOOD_LABELS.items()]


def mood_payload(mood: Mood) -> dict:
    focus = {"type": mood.focus_type, "value": mood.focus_value} if mood.focus_type else None
    return {
        "key": mood.key,
        "id": mood.id,
        "label": mood.label,
        "custom": True,
        "base_mood": mood.base_mood,
        "base_label": MOOD_LABELS[mood.base_mood],
        "focus": focus,
    }


def resolve_mood(db: Session, user: User | None, key: str) -> ResolvedMood:
    """Maps a built-in slug ("happy") or a custom key ("custom-12") to its filters."""
    key = key.strip().lower()
    if key in VALID_MOODS:
        return ResolvedMood(key, MOOD_LABELS[key], filters_for(key))

    if key.startswith("custom-") and key[7:].isdigit():
        if user is None:
            raise HTTPException(status_code=401, detail="Log in to use your custom moods.")
        mood = db.get(Mood, int(key[7:]))
        if mood is None or mood.user_id != user.id:
            raise HTTPException(status_code=404, detail="That mood no longer exists.")
        focus = (mood.focus_type, mood.focus_value) if mood.focus_type else None
        return ResolvedMood(mood.key, mood.label, filters_for(mood.base_mood, focus))

    raise HTTPException(
        status_code=400,
        detail=f"Unknown mood. Valid: {', '.join(sorted(VALID_MOODS))} or one of your custom moods",
    )


class MoodIn(BaseModel):
    label: str
    base_mood: str
    focus_type: str | None = None
    focus_value: str | None = None

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Give your mood a name.")
        if len(value) > 40:
            raise ValueError("Mood names can be at most 40 characters.")
        return value

    @field_validator("base_mood")
    @classmethod
    def _base(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in VALID_MOODS:
            raise ValueError("Pick one of the built-in moods to base it on.")
        return value


@router.get("")
def list_moods(user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    custom = []
    if user:
        custom = [mood_payload(m) for m in db.scalars(
            select(Mood).where(Mood.user_id == user.id).order_by(Mood.label_key)
        )]
    return {
        "builtin": builtin_payload(),
        "custom": custom,
        "focus_options": {"categories": list(CATEGORIES), "areas": list(AREAS)},
    }


@router.post("", status_code=201)
def add_mood(body: MoodIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    focus_type, focus_value = body.focus_type or None, (body.focus_value or "").strip() or None
    if bool(focus_type) != bool(focus_value):
        raise HTTPException(status_code=422, detail="Choose both a focus type and a value, or neither.")
    if focus_type and focus_value not in FOCUS_TYPES.get(focus_type, ()):
        raise HTTPException(status_code=422, detail="Unknown category or cuisine.")

    label_key = body.label.lower()
    if label_key in {label.lower() for label in MOOD_LABELS.values()}:
        raise HTTPException(status_code=409, detail=f'"{body.label}" is already a built-in mood.')
    if db.scalar(select(Mood).where(Mood.user_id == user.id, Mood.label_key == label_key)):
        raise HTTPException(status_code=409, detail=f'You already have a mood called "{body.label}".')
    count = db.scalar(select(func.count()).select_from(Mood).where(Mood.user_id == user.id))
    if count >= MAX_CUSTOM_MOODS:
        raise HTTPException(status_code=409, detail=f"You can have up to {MAX_CUSTOM_MOODS} custom moods.")

    mood = Mood(
        user_id=user.id,
        label=body.label,
        label_key=label_key,
        base_mood=body.base_mood,
        focus_type=focus_type,
        focus_value=focus_value,
    )
    db.add(mood)
    db.commit()
    return mood_payload(mood)


@router.delete("/{mood_id}")
def delete_mood(mood_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    mood = db.get(Mood, mood_id)
    if mood is None or mood.user_id != user.id:
        raise HTTPException(status_code=404, detail="Mood not found.")
    db.delete(mood)
    db.commit()
    return {"ok": True}
