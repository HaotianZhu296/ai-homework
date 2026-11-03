import os
import sys
import tempfile
from pathlib import Path

# Must be set before the app modules are imported.
_tmp = tempfile.mkdtemp(prefix="mood-recipes-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/default.db"
os.environ["BCRYPT_ROUNDS"] = "4"
os.environ.setdefault("DEV_SHOW_RESET_LINK", "1")
os.environ.pop("SMTP_HOST", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import db as db_module  # noqa: E402
import recipe_service  # noqa: E402
from app import app  # noqa: E402

FAKE_MEALS = {
    "100": {"id": "100", "name": "Test Pancakes", "category": "Breakfast", "area": "American",
            "image": "https://example.com/p.jpg", "instructions": "Mix. Fry.", "youtube": "https://youtu.be/x",
            "source": None, "ingredients": [{"ingredient": "Flour", "measure": "1 cup"}]},
    "200": {"id": "200", "name": "Test Curry", "category": "Chicken", "area": "Indian",
            "image": "https://example.com/c.jpg", "instructions": "Simmer.", "youtube": "",
            "source": "https://example.com/curry", "ingredients": []},
}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = db_module.make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    import models  # noqa: F401

    db_module.Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[db_module.get_db] = override_get_db

    # Never hit TheMealDB from tests.
    calls = []

    async def fake_get_recipe(filter_groups, exclude_ids):
        calls.append(filter_groups)
        for meal_id, meal in FAKE_MEALS.items():
            if meal_id not in exclude_ids:
                return meal
        return FAKE_MEALS["100"]

    async def fake_lookup(meal_id):
        if meal_id not in FAKE_MEALS:
            raise LookupError(meal_id)
        return FAKE_MEALS[meal_id]

    monkeypatch.setattr(recipe_service, "get_recipe", fake_get_recipe)
    monkeypatch.setattr(recipe_service, "lookup_meal", fake_lookup)

    with TestClient(app) as c:
        c.recipe_calls = calls
        c.Session = TestSession
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email="alice@example.com", password="correct horse"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r


@pytest.fixture()
def alice(client):
    register(client)
    return client
