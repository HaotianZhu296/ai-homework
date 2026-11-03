"""Saving recipes to a user's favorites, together with the mood they were saved under."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import recipe_service
from auth import require_user
from db import get_db
from models import Favorite, FavoriteMood, User, as_utc, utcnow
from moods import resolve_mood

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


class FavoriteIn(BaseModel):
    meal_id: str
    mood: str

    @field_validator("meal_id")
    @classmethod
    def _meal_id(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) > 10:
            raise ValueError("Invalid recipe id.")
        return value


def favorite_payload(fav: Favorite) -> dict:
    return {
        "id": fav.id,
        "meal_id": fav.meal_id,
        "name": fav.name,
        "category": fav.category,
        "area": fav.area,
        "image": fav.image,
        "youtube": fav.youtube,
        "source": fav.source,
        "instructions": fav.instructions,
        "ingredients": fav.ingredients or [],
        "created_at": as_utc(fav.created_at).isoformat(),
        "moods": [
            {"key": m.mood_key, "label": m.mood_label, "saved_at": as_utc(m.saved_at).isoformat()}
            for m in fav.moods
        ],
    }


def _user_favorite(db: Session, user: User, **where) -> Favorite | None:
    query = select(Favorite).where(Favorite.user_id == user.id).options(selectinload(Favorite.moods))
    for column, value in where.items():
        query = query.where(getattr(Favorite, column) == value)
    return db.scalar(query)


@router.get("")
def list_favorites(user: User = Depends(require_user), db: Session = Depends(get_db)):
    favorites = db.scalars(
        select(Favorite).where(Favorite.user_id == user.id).options(selectinload(Favorite.moods))
    ).all()
    # Most recently saved (under any mood) first.
    def last_saved(fav: Favorite):
        return max((as_utc(m.saved_at) for m in fav.moods), default=as_utc(fav.created_at))

    favorites = sorted(favorites, key=last_saved, reverse=True)
    return {"favorites": [favorite_payload(f) for f in favorites]}


@router.get("/status")
def favorite_status(meal_id: str = Query(...), user: User = Depends(require_user), db: Session = Depends(get_db)):
    fav = _user_favorite(db, user, meal_id=meal_id.strip())
    return {"saved": fav is not None, "id": fav.id if fav else None, "moods": [m.mood_key for m in fav.moods] if fav else []}


@router.post("")
async def save_favorite(
    body: FavoriteIn, response: Response, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    mood = resolve_mood(db, user, body.mood)
    fav = _user_favorite(db, user, meal_id=body.meal_id)

    if fav is None:
        # Look the recipe up ourselves rather than trusting recipe details from the client.
        try:
            meal = await recipe_service.lookup_meal(body.meal_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Recipe not found.") from None
        except Exception:
            raise HTTPException(status_code=502, detail="Recipe service unavailable.") from None
        fav = Favorite(
            user_id=user.id,
            meal_id=body.meal_id,
            name=meal.get("name") or "Recipe",
            category=meal.get("category"),
            area=meal.get("area"),
            image=meal.get("image"),
            youtube=(meal.get("youtube") or "").strip() or None,
            source=(meal.get("source") or "").strip() or None,
            instructions=meal.get("instructions"),
            ingredients=meal.get("ingredients") or [],
        )
        db.add(fav)
        response.status_code = 201

    existing = next((m for m in fav.moods if m.mood_key == mood.key), None)
    if existing:
        existing.saved_at = utcnow()
        existing.mood_label = mood.label
    else:
        fav.moods.append(FavoriteMood(mood_key=mood.key, mood_label=mood.label))
    db.commit()
    db.refresh(fav)
    return favorite_payload(fav)


@router.delete("/{favorite_id}")
def remove_favorite(favorite_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    fav = _user_favorite(db, user, id=favorite_id)
    if fav is None:
        raise HTTPException(status_code=404, detail="Favorite not found.")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.delete("/{favorite_id}/moods/{mood_key}")
def remove_favorite_mood(
    favorite_id: int, mood_key: str, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    """Untags one mood; the favorite itself goes away with its last mood."""
    fav = _user_favorite(db, user, id=favorite_id)
    if fav is None:
        raise HTTPException(status_code=404, detail="Favorite not found.")
    tag = next((m for m in fav.moods if m.mood_key == mood_key), None)
    if tag is None:
        raise HTTPException(status_code=404, detail="That mood is not on this favorite.")
    fav.moods.remove(tag)
    removed = not fav.moods
    if removed:
        db.delete(fav)
    db.commit()
    return {"ok": True, "removed": removed}
