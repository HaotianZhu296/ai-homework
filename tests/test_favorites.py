from tests.conftest import register


def test_favorites_require_login(client):
    assert client.get("/api/favorites").status_code == 401
    assert client.post("/api/favorites", json={"meal_id": "100", "mood": "happy"}).status_code == 401


def test_save_and_list_favorite(alice):
    r = alice.post("/api/favorites", json={"meal_id": "100", "mood": "energized"})
    assert r.status_code == 201, r.text
    fav = r.json()
    # Details come from the server-side lookup, not the client.
    assert fav["name"] == "Test Pancakes"
    assert fav["ingredients"] == [{"ingredient": "Flour", "measure": "1 cup"}]
    assert [m["label"] for m in fav["moods"]] == ["Energized"]

    listed = alice.get("/api/favorites").json()["favorites"]
    assert len(listed) == 1 and listed[0]["meal_id"] == "100"
    assert alice.get("/api/favorites/status", params={"meal_id": "100"}).json()["moods"] == ["energized"]
    assert alice.get("/api/favorites/status", params={"meal_id": "200"}).json()["saved"] is False


def test_same_recipe_under_several_moods(alice):
    alice.post("/api/favorites", json={"meal_id": "100", "mood": "energized"})
    again = alice.post("/api/favorites", json={"meal_id": "100", "mood": "energized"})
    assert again.status_code == 200
    custom = alice.post("/api/moods", json={"label": "Sunday brunch", "base_mood": "energized"}).json()
    second = alice.post("/api/favorites", json={"meal_id": "100", "mood": custom["key"]}).json()
    assert [m["label"] for m in second["moods"]] == ["Energized", "Sunday brunch"]
    assert len(alice.get("/api/favorites").json()["favorites"]) == 1

    # Deleting the custom mood keeps the label on the saved favorite.
    alice.delete(f"/api/moods/{custom['id']}")
    labels = [m["label"] for m in alice.get("/api/favorites").json()["favorites"][0]["moods"]]
    assert labels == ["Energized", "Sunday brunch"]


def test_newest_saved_first(alice):
    alice.post("/api/favorites", json={"meal_id": "100", "mood": "happy"})
    alice.post("/api/favorites", json={"meal_id": "200", "mood": "comfort"})
    assert [f["meal_id"] for f in alice.get("/api/favorites").json()["favorites"]] == ["200", "100"]


def test_save_validation(alice):
    assert alice.post("/api/favorites", json={"meal_id": "abc", "mood": "happy"}).status_code == 422
    assert alice.post("/api/favorites", json={"meal_id": "999", "mood": "happy"}).status_code == 404
    assert alice.post("/api/favorites", json={"meal_id": "100", "mood": "grumpy"}).status_code == 400


def test_remove_mood_then_favorite(alice):
    fav = alice.post("/api/favorites", json={"meal_id": "100", "mood": "happy"}).json()
    alice.post("/api/favorites", json={"meal_id": "100", "mood": "lazy"})
    r = alice.delete(f"/api/favorites/{fav['id']}/moods/happy")
    assert r.json() == {"ok": True, "removed": False}
    r = alice.delete(f"/api/favorites/{fav['id']}/moods/lazy")
    assert r.json() == {"ok": True, "removed": True}
    assert alice.get("/api/favorites").json()["favorites"] == []

    fav = alice.post("/api/favorites", json={"meal_id": "200", "mood": "comfort"}).json()
    assert alice.delete(f"/api/favorites/{fav['id']}").status_code == 200
    assert alice.delete(f"/api/favorites/{fav['id']}").status_code == 404


def test_favorites_are_per_user(client):
    register(client, "alice@example.com")
    fav = client.post("/api/favorites", json={"meal_id": "100", "mood": "happy"}).json()
    client.post("/api/auth/logout")

    register(client, "bob@example.com")
    assert client.get("/api/favorites").json()["favorites"] == []
    assert client.delete(f"/api/favorites/{fav['id']}").status_code == 404
    bob_fav = client.post("/api/favorites", json={"meal_id": "100", "mood": "comfort"})
    assert bob_fav.status_code == 201  # separate row linked to Bob
    assert bob_fav.json()["id"] != fav["id"]
