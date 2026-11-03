import sqlite3
from collections import Counter

import pytest

import analysis
from import_data import SAMPLE_CSV, import_csv, parse_annotations


def test_parse_annotations_formats():
    assert parse_annotations('["Negative", "neutral", " POSITIVE "]') == ["negative", "neutral", "positive"]
    assert parse_annotations("negative, neutral, sarcastic") == ["negative", "neutral", "sarcastic"]
    with pytest.raises(ValueError):
        parse_annotations('["negative", "neutral"]')
    with pytest.raises(ValueError):
        parse_annotations('["negative", "neutral", "angry"]')
    with pytest.raises(ValueError):
        parse_annotations('{"a": 1}')


def test_import_is_idempotent_and_builds_sentence_pool(conn, small_csv):
    first = import_csv(conn, small_csv)
    assert (first.inserted, first.existing, first.skipped) == (4, 0, [])
    second = import_csv(conn, small_csv)
    assert (second.inserted, second.existing) == (0, 4)
    assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0] == 4
    row = conn.execute("SELECT * FROM annotations WHERE id = 4").fetchone()
    assert row["text"] == "Oh sure, best idea ever."
    assert [row["annotator_1"], row["annotator_2"], row["annotator_3"]] == ["sarcastic", "sarcastic", "positive"]
    assert row["source"] == "dataset"


def test_import_skips_bad_rows(conn, tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        'id,text,annotations\n1,Fine.,"[""neutral"",""neutral"",""neutral""]"\n'
        'x,Bad id,"[]"\n3,,"[""neutral"",""neutral"",""neutral""]"\n4,Two labels,"[""neutral"",""neutral""]"\n',
        encoding="utf-8",
    )
    result = import_csv(conn, path)
    assert result.inserted == 1
    assert len(result.skipped) == 3


def test_bundled_sample_matches_expected_shape(conn):
    result = import_csv(conn, SAMPLE_CSV)
    assert result.inserted == 1000 and not result.skipped
    assert conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0] == 20


def test_annotations_are_immutable(conn, small_csv):
    import_csv(conn, small_csv)
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("UPDATE annotations SET annotator_1 = 'neutral' WHERE id = 1")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        conn.execute("DELETE FROM annotations WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO annotations (sentence_id, text, annotator_1, annotator_2, annotator_3, source) "
            "VALUES (1, 'x', 'angry', 'neutral', 'neutral', 'ui')"
        )


def test_resolve_majority_and_agreement():
    assert analysis.resolve(["negative", "negative", "positive"]) == ("negative", pytest.approx(2 / 3))
    assert analysis.resolve(["neutral"] * 3) == ("neutral", 1.0)


def test_resolve_three_way_tie():
    votes = ["positive", "negative", "sarcastic"]
    # Without context: fixed label order.
    assert analysis.resolve(votes) == ("positive", pytest.approx(1 / 3))
    # With context: the label this sentence usually gets.
    assert analysis.resolve(votes, Counter(sarcastic=10, positive=2))[0] == "sarcastic"


def test_classifier_run_is_stored_and_reproducible(conn):
    import_csv(conn, SAMPLE_CSV)
    first = analysis.train_and_store(conn, seed=7)
    run1 = analysis.latest_run(conn)
    second = analysis.train_and_store(conn, seed=7)
    run2 = analysis.latest_run(conn)
    assert second == first + 1
    assert run1["accuracy"] == run2["accuracy"]
    assert run1["n_test"] == 200 and run1["n_train"] == 800
    assert len(run1["predictions"]) == 1000
    assert sum(p["in_test"] for p in run1["predictions"].values()) == 200
    assert "precision" in run1["report_text"] and "accuracy" in run1["report_text"]
    # Noisy labels cap accuracy, but the model must beat the majority-class baseline.
    records = analysis.load_records(conn)
    baseline = max(Counter(r.resolved for r in records).values()) / len(records)
    assert run1["accuracy"] > baseline


def test_sentence_holdout_keeps_sentences_together(conn):
    import_csv(conn, SAMPLE_CSV)
    analysis.train_and_store(conn, seed=3, split="sentences")
    run = analysis.latest_run(conn)
    records = {r.id: r.text for r in analysis.load_records(conn)}
    test_texts = {records[i] for i, p in run["predictions"].items() if p["in_test"]}
    train_texts = {records[i] for i, p in run["predictions"].items() if not p["in_test"]}
    assert test_texts and not (test_texts & train_texts)


def test_classifier_needs_enough_data(conn, small_csv):
    import_csv(conn, small_csv)
    with pytest.raises(analysis.ClassifierError, match="at least"):
        analysis.train_and_store(conn)
