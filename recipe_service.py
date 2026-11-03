"""TheMealDB-backed recipe selection by mood."""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

BASE = "https://www.themealdb.com/api/json/v1/1"

# Mood slug -> list of (filter_param, value) for filter.php — c=category, a=area
# Each mood uses many buckets so the merged pool is large; meal IDs are deduped in order
# (first-seen wins) so each id appears at most once per mood.
MOOD_FILTERS: dict[str, list[tuple[str, str]]] = {
    "happy": [
        ("c", "Dessert"),
        ("c", "Pasta"),
        ("c", "Starter"),
        ("c", "Side"),
        ("c", "Miscellaneous"),
    ],
    "comfort": [
        ("c", "Beef"),
        ("c", "Chicken"),
        ("c", "Lamb"),
        ("c", "Pork"),
        ("c", "Goat"),
    ],
    "energized": [
        ("c", "Breakfast"),
        ("c", "Seafood"),
        ("c", "Vegetarian"),
        ("c", "Vegan"),
    ],
    "cozy": [
        ("a", "British"),
        ("a", "Irish"),
        ("a", "American"),
        ("a", "Italian"),
        ("a", "Canadian"),
        ("a", "French"),
    ],
    "adventurous": [
        ("a", "Thai"),
        ("a", "Indian"),
        ("a", "Mexican"),
        ("a", "Japanese"),
        ("a", "Chinese"),
        ("a", "Moroccan"),
        ("a", "Spanish"),
        ("a", "Vietnamese"),
        ("a", "Greek"),
        ("a", "Turkish"),
        ("a", "Tunisian"),
        ("a", "Malaysian"),
    ],
    "sweet": [
        ("c", "Dessert"),
    ],
    "festive": [
        ("c", "Lamb"),
        ("c", "Goat"),
        ("c", "Dessert"),
        ("a", "Jamaican"),
        ("a", "Mexican"),
    ],
    "lazy": [
        ("c", "Pasta"),
        ("c", "Side"),
        ("c", "Breakfast"),
        ("c", "Starter"),
    ],
    "romantic": [
        ("a", "French"),
        ("a", "Italian"),
        ("c", "Seafood"),
    ],
}

MOOD_LABELS: dict[str, str] = {slug: slug.capitalize() for slug in MOOD_FILTERS}

VALID_MOODS = frozenset(MOOD_FILTERS.keys())

# Values a custom mood may use as its optional "focus" (TheMealDB categories and a
# selection of cuisines).
CATEGORIES = (
    "Beef", "Breakfast", "Chicken", "Dessert", "Goat", "Lamb", "Miscellaneous",
    "Pasta", "Pork", "Seafood", "Side", "Starter", "Vegan", "Vegetarian",
)
AREAS = (
    "American", "British", "Canadian", "Chinese", "Croatian", "Dutch", "Egyptian",
    "Filipino", "French", "Greek", "Indian", "Irish", "Italian", "Jamaican", "Japanese",
    "Kenyan", "Malaysian", "Mexican", "Moroccan", "Polish", "Portuguese", "Russian",
    "Spanish", "Thai", "Tunisian", "Turkish", "Ukrainian", "Vietnamese",
)

# filter.php results change rarely; cache them so a recipe request does not refetch
# every bucket for the mood.
_FILTER_TTL_SECONDS = 60 * 60
_filter_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}


async def _fetch_filter_meal_ids(client: httpx.AsyncClient, param: str, value: str) -> list[str]:
    cached = _filter_cache.get((param, value))
    if cached and time.monotonic() - cached[0] < _FILTER_TTL_SECONDS:
        return cached[1]
    r = await client.get(f"{BASE}/filter.php", params={param: value})
    r.raise_for_status()
    data = r.json()
    meals = data.get("meals") or []
    out: list[str] = []
    for m in meals:
        mid = m.get("idMeal")
        if mid:
            out.append(str(mid))
    _filter_cache[(param, value)] = (time.monotonic(), out)
    return out


async def collect_meal_ids(client: httpx.AsyncClient, filters: list[tuple[str, str]]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for param, value in filters:
        for mid in await _fetch_filter_meal_ids(client, param, value):
            if mid not in seen:
                seen.add(mid)
                ordered.append(mid)
    return ordered


async def collect_meal_ids_for_mood(client: httpx.AsyncClient, mood: str) -> list[str]:
    return await collect_meal_ids(client, MOOD_FILTERS.get(mood, []))


def _meal_to_payload(meal: dict[str, Any]) -> dict[str, Any]:
    ingredients: list[dict[str, str]] = []
    for i in range(1, 21):
        ing = meal.get(f"strIngredient{i}") or ""
        meas = meal.get(f"strMeasure{i}") or ""
        ing = ing.strip()
        if ing:
            ingredients.append({"ingredient": ing, "measure": meas.strip()})

    return {
        "id": meal.get("idMeal"),
        "name": meal.get("strMeal"),
        "category": meal.get("strCategory"),
        "area": meal.get("strArea"),
        "image": meal.get("strMealThumb"),
        "instructions": meal.get("strInstructions"),
        "youtube": meal.get("strYoutube"),
        "source": meal.get("strSource"),
        "ingredients": ingredients,
    }


async def _lookup_meal(client: httpx.AsyncClient, meal_id: str) -> dict[str, Any]:
    r = await client.get(f"{BASE}/lookup.php", params={"i": meal_id})
    r.raise_for_status()
    data = r.json()
    meals = data.get("meals") or []
    if not meals:
        raise LookupError(f"No meal for id {meal_id}")
    return _meal_to_payload(meals[0])


async def _random_meal_any(client: httpx.AsyncClient) -> dict[str, Any]:
    r = await client.get(f"{BASE}/random.php")
    r.raise_for_status()
    data = r.json()
    meals = data.get("meals") or []
    if not meals:
        raise ValueError("random.php returned no meal")
    return _meal_to_payload(meals[0])


async def lookup_meal(meal_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        return await _lookup_meal(client, meal_id)


def filters_for(base_mood: str, focus: tuple[str, str] | None = None) -> list[list[tuple[str, str]]]:
    """Ordered filter groups to try: the custom focus first (if any), then the base mood."""
    groups = [[focus]] if focus else []
    groups.append(MOOD_FILTERS[base_mood])
    return groups


async def get_recipe(filter_groups: list[list[tuple[str, str]]], exclude_ids: set[str]) -> dict[str, Any]:
    """Picks a random meal from the first filter group that has unseen meals."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        first_pool: list[str] = []
        for filters in filter_groups:
            pool = await collect_meal_ids(client, filters)
            first_pool = first_pool or pool
            candidates = [mid for mid in pool if mid not in exclude_ids]
            if candidates:
                return await _lookup_meal(client, random.choice(candidates))

        if first_pool:
            # Every matching meal was already shown; start over within the same mood.
            return await _lookup_meal(client, random.choice(first_pool))

        # No meals from filters (empty category / API); fallback
        return await _random_meal_any(client)


async def get_recipe_for_mood(mood: str, exclude_ids: set[str]) -> dict[str, Any]:
    mood = mood.lower().strip()
    if mood not in VALID_MOODS:
        raise ValueError(f"Unknown mood: {mood}")
    return await get_recipe(filters_for(mood), exclude_ids)
