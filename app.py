"""Mood-based recipe app: static UI + /api/recipe proxy to TheMealDB, with accounts."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import favorites
import moods
import recipe_service
from auth import current_user
from db import get_db, init_db
from models import User
from moods import resolve_mood

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Mood Recipes", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(moods.router)
app.include_router(favorites.router)


@app.get("/api/recipe")
async def api_recipe(
    mood: str = Query(..., description="Built-in mood slug (happy, comfort, …) or a custom mood key (custom-<id>)"),
    exclude: str | None = Query(None, description="Comma-separated meal ids to avoid"),
    user: User | None = Depends(current_user),
    db: Session = Depends(get_db),
):
    exclude_ids: set[str] = set()
    if exclude:
        exclude_ids = {x.strip() for x in exclude.split(",") if x.strip()}

    resolved = resolve_mood(db, user, mood)

    try:
        recipe = await recipe_service.get_recipe(resolved.filter_groups, exclude_ids)
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"detail": "Recipe service unavailable.", "error": str(e)},
        )

    return {**recipe, "mood": {"key": resolved.key, "label": resolved.label}}


app.mount(
    "/",
    StaticFiles(directory=str(STATIC_DIR), html=True),
    name="static",
)
