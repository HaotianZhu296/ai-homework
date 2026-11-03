def _sentence(client):
    r = client.get("/api/sentence/random")
    assert r.status_code == 200
    return r.json()


def test_bootstrap_imports_dataset_and_trains(client):
    stats = client.get("/api/stats").json()
    assert stats["summary"]["total_records"] == 1000
    assert stats["summary"]["unique_texts"] == 20
    assert 0 < stats["summary"]["average_agreement"] <= 1
    assert stats["classifier"]["seed"] == 42
    assert stats["summary"]["classifier_accuracy"] == stats["classifier"]["accuracy"]
    first = stats["records"][0]
    assert set(first) >= {"id", "text", "annotations", "resolved", "agreement", "prediction", "confidence"}
    assert len(stats["sentences"]) == 20


def test_random_sentence_and_exclude(client):
    s = _sentence(client)
    assert s["text"] and s["times_annotated"] > 0
    for _ in range(10):
        assert client.get("/api/sentence/random", params={"exclude": s["id"]}).json()["id"] != s["id"]


def test_save_requires_all_three_valid_labels(client):
    s = _sentence(client)
    two = client.post("/api/annotations", json={"sentence_id": s["id"], "labels": ["positive", "neutral"]})
    assert two.status_code == 422
    bad = client.post("/api/annotations", json={"sentence_id": s["id"], "labels": ["positive", "neutral", "angry"]})
    assert bad.status_code == 422
    unknown = client.post("/api/annotations", json={"sentence_id": 99999, "labels": ["positive"] * 3})
    assert unknown.status_code == 404


def test_save_annotation_and_see_it_in_stats(client):
    s = _sentence(client)
    r = client.post("/api/annotations", json={
        "sentence_id": s["id"], "labels": ["Negative", "negative", "sarcastic"], "client_key": "draw-1",
    })
    assert r.status_code == 201, r.text
    saved = r.json()
    assert saved["id"] == 1001
    assert saved["text"] == s["text"]
    assert saved["annotations"] == ["negative", "negative", "sarcastic"]
    assert saved["resolved"] == "negative"
    assert abs(saved["agreement"] - 2 / 3) < 1e-9
    assert saved["source"] == "ui"

    stats = client.get("/api/stats").json()
    assert stats["summary"]["total_records"] == 1001
    assert stats["summary"]["ui_records"] == 1
    assert stats["classifier"]["new_since_run"] == 1
    row = next(x for x in stats["records"] if x["id"] == 1001)
    assert row["prediction"] is None  # not part of the last run yet


def test_saved_annotations_cannot_change(client):
    s = _sentence(client)
    body = {"sentence_id": s["id"], "labels": ["positive"] * 3, "client_key": "same-draw"}
    assert client.post("/api/annotations", json=body).status_code == 201
    again = client.post("/api/annotations", json={**body, "labels": ["negative"] * 3})
    assert again.status_code == 409
    assert client.put("/api/annotations", json=body).status_code == 405
    assert client.delete("/api/annotations").status_code == 405
    assert client.get("/api/stats").json()["summary"]["ui_records"] == 1


def test_rerun_classifier(client):
    before = client.get("/api/stats").json()["classifier"]
    s = _sentence(client)
    client.post("/api/annotations", json={"sentence_id": s["id"], "labels": ["neutral"] * 3})

    r = client.post("/api/classifier/run", json={"split": "records"})
    assert r.status_code == 200
    run = r.json()
    assert run["id"] == before["id"] + 1
    after = client.get("/api/stats").json()
    assert after["classifier"]["n_records"] == 1001
    assert after["classifier"]["new_since_run"] == 0
    assert [h["id"] for h in after["history"]][:2] == [run["id"], before["id"]]

    fixed = client.post("/api/classifier/run", json={"seed": 11}).json()
    again = client.post("/api/classifier/run", json={"seed": 11}).json()
    assert fixed["accuracy"] == again["accuracy"]

    held = client.post("/api/classifier/run", json={"split": "sentences"})
    assert held.status_code == 200 and held.json()["split"] == "sentences"
    assert client.post("/api/classifier/run", json={"split": "bogus"}).status_code == 400


def test_pages_are_served(client):
    for path in ("/", "/stats.html"):
        r = client.get(path)
        assert r.status_code == 200 and "Multi-Annotator" in r.text
