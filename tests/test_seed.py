import json
from pathlib import Path

import pytest

import seed_index

DATA = Path(__file__).resolve().parent.parent / "data" / "sample-movies.bulk"


def test_mapping_matches_assignment():
    props = seed_index.load_mapping()["mappings"]["properties"]
    assert props["title"]["type"] == "text"  # full-text searchable
    assert props["plot"]["index"] is False  # stored, not indexed
    assert props["rating"]["type"] == "float"  # mixed int/float in the data
    for field in ("rating", "year", "genres", "actors", "directors"):
        assert props[field].get("index", True) is True
    assert seed_index.load_mapping()["mappings"]["dynamic"] is False


def test_sample_file_is_valid_bulk():
    body, count = seed_index.prepare_bulk_body(DATA.read_text(encoding="utf-8"))
    assert count == 1250
    assert body.endswith("\n")  # the raw file has no trailing newline
    lines = body.splitlines()
    assert len(lines) == 2 * count
    action, doc = json.loads(lines[0]), json.loads(lines[1])
    assert action["index"]["_index"] == "movies"
    assert action["index"]["_id"] == doc["id"]
    assert "type" not in doc


def test_index_and_id_are_normalised():
    text = '{"index": {"_index": "other"}}\n{"id": "tt1", "title": "A", "type": "add"}'
    body, count = seed_index.prepare_bulk_body(text)
    action, doc = (json.loads(line) for line in body.splitlines())
    assert count == 1
    assert action == {"index": {"_index": "movies", "_id": "tt1"}}
    assert doc == {"id": "tt1", "title": "A"}


@pytest.mark.parametrize(
    "text",
    [
        "",
        '{"index": {}}',
        '{"index": {}}\n{not json}',
        '{"delete": {"_id": "1"}}\n{"title": "x"}',
    ],
)
def test_bad_bulk_files_are_rejected(text):
    with pytest.raises(ValueError):
        seed_index.prepare_bulk_body(text)
