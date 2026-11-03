# Homework 0-2 — Development Plan

Goal: extend the Mood Recipes starter (FastAPI + static Tailwind UI + TheMealDB) with user
accounts, favorite recipes stored per user, and user-defined moods.

## 0. Starter cleanup
- [x] Restore the starter's mislabeled files (`app.py` / `recipe_service.py` / `static/script.js`) and add a real `requirements.txt`
- [x] Fix starter bugs: the "Sweet" button has no backend mood (HTTP 400); the empty-pool fallback calls `_random_meal_any` with the wrong arguments
- [x] Cache TheMealDB filter lookups so each recipe request does not re-download every category

## 1. Persistence layer
- [x] SQLAlchemy 2.0 + SQLite (`DATABASE_URL` overrides the default file)
- [x] Models: `User`, `AuthSession`, `PasswordResetToken`, `Mood`, `Favorite`, `FavoriteMood`
- [x] Tables created on startup

## 2. Authentication
- [x] Register (email + password, min 8 chars), passwords hashed with **bcrypt**
- [x] Login with "Remember me" (30-day persistent cookie vs. browser-session cookie)
- [x] Sessions are random tokens; only a SHA-256 hash is stored, cookie is `HttpOnly` + `SameSite=Lax`
- [x] Logout revokes the session server-side
- [x] Forgot password → single-use reset token (hashed, 30-minute expiry) → reset page; all sessions revoked after reset
- [x] Reset link is emailed when SMTP is configured, otherwise logged (and shown on screen in dev mode)
- [x] Basic brute-force protection: temporary lockout after repeated failed logins
- [x] UI based on the provided login mock-up: login, register, forgot-password, reset-password pages

## 3. Favorites
- [x] `POST /api/favorites` — server looks the recipe up itself (client only sends `meal_id` + mood)
- [x] One favorite per user + recipe; saving it under another mood adds that mood to it
- [x] `favorites.html` — recipe cards with every associated mood and when it was saved, mood filter, video/source links, expandable recipe, remove

## 4. Custom moods
- [x] Users add moods with a label, a "based on" built-in mood, and an optional category/cuisine focus
- [x] Recipe selection resolves custom moods → focus filter first, then the base mood's filters
- [x] Custom moods appear alongside built-ins and can be deleted; they are private to each user

## 5. Quality
- [x] pytest suite (auth, reset flow, moods, favorites, recipe selection with TheMealDB mocked)
- [x] Browser end-to-end check of every page
- [x] README with setup and API reference
