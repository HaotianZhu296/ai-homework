"""SQLite storage. Annotations are append-only: triggers reject UPDATE and DELETE."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ANNOTATOR_DB", BASE_DIR / "annotations.db"))

LABELS = ("positive", "neutral", "negative", "sarcastic")

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS sentences (
    id   INTEGER PRIMARY KEY,
    text TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS annotations (
    id          INTEGER PRIMARY KEY,
    sentence_id INTEGER NOT NULL REFERENCES sentences(id),
    text        TEXT NOT NULL,
    annotator_1 TEXT NOT NULL CHECK (annotator_1 IN {LABELS}),
    annotator_2 TEXT NOT NULL CHECK (annotator_2 IN {LABELS}),
    annotator_3 TEXT NOT NULL CHECK (annotator_3 IN {LABELS}),
    source      TEXT NOT NULL CHECK (source IN ('dataset', 'ui')),
    client_key  TEXT UNIQUE,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TRIGGER IF NOT EXISTS annotations_immutable_update
BEFORE UPDATE ON annotations
BEGIN
    SELECT RAISE(ABORT, 'annotations are immutable');
END;

CREATE TRIGGER IF NOT EXISTS annotations_immutable_delete
BEFORE DELETE ON annotations
BEGIN
    SELECT RAISE(ABORT, 'annotations are immutable');
END;

CREATE TABLE IF NOT EXISTS classifier_runs (
    id           INTEGER PRIMARY KEY,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    seed         INTEGER NOT NULL,
    split        TEXT NOT NULL,
    n_records    INTEGER NOT NULL,
    n_train      INTEGER NOT NULL,
    n_test       INTEGER NOT NULL,
    accuracy     REAL NOT NULL,
    report_text  TEXT NOT NULL,
    report_json  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    run_id        INTEGER NOT NULL REFERENCES classifier_runs(id),
    annotation_id INTEGER NOT NULL REFERENCES annotations(id),
    predicted     TEXT NOT NULL,
    confidence    REAL NOT NULL,
    in_test       INTEGER NOT NULL,
    PRIMARY KEY (run_id, annotation_id)
);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def sentence_id(conn: sqlite3.Connection, text: str) -> int:
    conn.execute("INSERT OR IGNORE INTO sentences (text) VALUES (?)", (text,))
    return conn.execute("SELECT id FROM sentences WHERE text = ?", (text,)).fetchone()["id"]
