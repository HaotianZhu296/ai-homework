from recipe_service import MOOD_FILTERS
from tests.conftest import register


def test_builtin_moods_are_public(client):
    body = client.get("/api/moods").json()
    keys = [m["key"] for m in body["builtin"]]
    assert "happy" in keys and "sweet" in keys
    assert body["custom"] == []
    assert "Breakfast" in body["focus_options"]["categories"]


def test_every_builtin_mood_returns_a_recipe(client):
    for key in MOOD_FILTERS:
        r = client.get("/api/recipe", params={"mood": key})
        assert r.status_code == 200, key
        assert r.json()["mood"]["key"] == key


def test_unknown_mood_is_rejected(client):
    assert client.get("/api/recipe", params={"mood": "grumpy"}).status_code == 400


def test_adding_a_mood_requires_login(client):
    r = client.post("/api/moods", json={"label": "Brunch", "base_mood": "energized"})
    assert r.status_code == 401


def test_add_list_and_use_custom_mood(alice):
    r = alice.post("/api/moods", json={
        "label": "  Sunday   brunch ", "base_mood": "energized", "focus_type": "c", "focus_value": "Breakfast",
    })
    assert r.status_code == 201, r.text
    mood = r.json()
    assert mood["label"] == "Sunday brunch"
    assert mood["key"] == f"custom-{mood['id']}"
    assert mood["focus"] == {"type": "c", "value": "Breakfast"}

    custom = alice.get("/api/moods").json()["custom"]
    assert [m["label"] for m in custom] == ["Sunday brunch"]

    recipe = alice.get("/api/recipe", params={"mood": mood["key"]})
    assert recipe.status_code == 200
    assert recipe.json()["mood"]["label"] == "Sunday brunch"
    # Selection tries the focus first, then falls back to the base mood's filters.
    assert alice.recipe_calls[-1] == [[("c", "Breakfast")], MOOD_FILTERS["energized"]]


def test_custom_mood_without_focus_uses_base_filters(alice):
    mood = alice.post("/api/moods", json={"label": "Rainy day", "base_mood": "cozy"}).json()
    alice.get("/api/recipe", params={"mood": mood["key"]})
    assert alice.recipe_calls[-1] == [MOOD_FILTERS["cozy"]]


def test_mood_validation(alice):
    assert alice.post("/api/moods", json={"label": "", "base_mood": "happy"}).status_code == 422
    assert alice.post("/api/moods", json={"label": "x" * 41, "base_mood": "happy"}).status_code == 422
    assert alice.post("/api/moods", json={"label": "Ok", "base_mood": "grumpy"}).status_code == 422
    assert alice.post("/api/moods", json={"label": "Happy", "base_mood": "happy"}).status_code == 409
    bad_focus = {"label": "Ok", "base_mood": "happy", "focus_type": "c", "focus_value": "Pizza"}
    assert alice.post("/api/moods", json=bad_focus).status_code == 422
    half_focus = {"label": "Ok", "base_mood": "happy", "focus_type": "c"}
    assert alice.post("/api/moods", json=half_focus).status_code == 422
    assert alice.post("/api/moods", json={"label": "Late night", "base_mood": "lazy"}).status_code == 201
    assert alice.post("/api/moods", json={"label": "late NIGHT", "base_mood": "lazy"}).status_code == 409


def test_custom_moods_are_private(client):
    register(client, "alice@example.com")
    mood = client.post("/api/moods", json={"label": "Secret", "base_mood": "happy"}).json()
    client.post("/api/auth/logout")

    assert client.get("/api/recipe", params={"mood": mood["key"]}).status_code == 401

    register(client, "bob@example.com")
    assert client.get("/api/moods").json()["custom"] == []
    assert client.get("/api/recipe", params={"mood": mood["key"]}).status_code == 404
    assert client.delete(f"/api/moods/{mood['id']}").status_code == 404


def test_delete_mood(alice):
    mood = alice.post("/api/moods", json={"label": "Gone soon", "base_mood": "comfort"}).json()
    assert alice.delete(f"/api/moods/{mood['id']}").status_code == 200
    assert alice.get("/api/moods").json()["custom"] == []
    assert alice.get("/api/recipe", params={"mood": mood["key"]}).status_code == 404
