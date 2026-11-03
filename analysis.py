"""Label resolution, inter-annotator agreement, and the sentiment classifier."""

from __future__ import annotations

import json
import random
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.pipeline import FeatureUnion, make_pipeline

from db import LABELS

SPLITS = ("records", "sentences")
MIN_RECORDS = 10
TEST_SIZE = 0.2


def _votes(row: sqlite3.Row) -> list[str]:
    return [row["annotator_1"], row["annotator_2"], row["annotator_3"]]


def resolve(votes: list[str], fallback: Counter | None = None) -> tuple[str, float]:
    """Majority label and agreement (share of annotators who chose it).

    A three-way split is broken by how this sentence was labelled across all records
    (`fallback`), then by the fixed LABELS order, so the result is deterministic.
    """
    counts = Counter(votes)
    top = max(counts.values())
    tied = [label for label in LABELS if counts.get(label) == top]
    if len(tied) > 1 and fallback:
        best = max(fallback.get(label, 0) for label in tied)
        tied = [label for label in tied if fallback.get(label, 0) == best]
    return tied[0], top / len(votes)


def text_vote_counts(rows: list[sqlite3.Row]) -> dict[str, Counter]:
    pooled: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        pooled[row["text"]].update(_votes(row))
    return pooled


@dataclass
class Record:
    id: int
    text: str
    votes: list[str]
    resolved: str
    agreement: float
    source: str
    created_at: str


def load_records(conn: sqlite3.Connection) -> list[Record]:
    rows = conn.execute("SELECT * FROM annotations ORDER BY id").fetchall()
    pooled = text_vote_counts(rows)
    records = []
    for row in rows:
        resolved, agreement = resolve(_votes(row), pooled[row["text"]])
        records.append(Record(row["id"], row["text"], _votes(row), resolved, agreement,
                              row["source"], row["created_at"]))
    return records


def sentence_summary(records: list[Record]) -> list[dict]:
    """Per unique sentence: all votes pooled across its records."""
    grouped: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        grouped[record.text].append(record)
    out = []
    for text, group in grouped.items():
        votes = Counter(v for r in group for v in r.votes)
        total = sum(votes.values())
        label, count = max(((label, votes.get(label, 0)) for label in LABELS), key=lambda item: item[1])
        out.append({
            "text": text,
            "records": len(group),
            "resolved": label,
            "agreement": count / total,
            "record_agreement": sum(r.agreement for r in group) / len(group),
            "votes": {label: votes.get(label, 0) for label in LABELS},
        })
    return sorted(out, key=lambda s: s["text"].lower())


# ---- classifier --------------------------------------------------------------------------

def build_model(seed: int):
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), lowercase=True, sublinear_tf=True)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True, sublinear_tf=True)),
    ])
    return make_pipeline(features, LogisticRegression(max_iter=2000, class_weight="balanced", random_state=seed))


def _split(records: list[Record], split: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    indices = np.arange(len(records))
    labels = [r.resolved for r in records]
    if split == "sentences":
        groups = [r.text for r in records]
        if len(set(groups)) < 2:
            raise ValueError("Holding out whole sentences needs at least 2 distinct sentences.")
        splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=seed)
        train, test = next(splitter.split(indices, labels, groups))
        return train, test
    counts = Counter(labels)
    stratify = labels if min(counts.values()) >= 2 else None
    train, test = train_test_split(indices, test_size=TEST_SIZE, random_state=seed, stratify=stratify)
    return train, test


class ClassifierError(ValueError):
    pass


def train_and_store(conn: sqlite3.Connection, seed: int | None = None, split: str = "records") -> int:
    """Trains on resolved labels, evaluates on a held-out split, stores the run. Returns its id."""
    if split not in SPLITS:
        raise ClassifierError(f"split must be one of {SPLITS}")
    records = load_records(conn)
    if len(records) < MIN_RECORDS:
        raise ClassifierError(f"Need at least {MIN_RECORDS} saved annotations to train (have {len(records)}).")
    if len({r.resolved for r in records}) < 2:
        raise ClassifierError("Need at least two different resolved labels to train.")

    seed = random.randrange(1, 1_000_000) if seed is None else seed
    try:
        train, test = _split(records, split, seed)
    except ValueError as err:
        raise ClassifierError(str(err)) from err
    texts = np.array([r.text for r in records], dtype=object)
    labels = np.array([r.resolved for r in records], dtype=object)
    if len(set(labels[train])) < 2:
        raise ClassifierError("The training split only contains one label; try another run.")

    model = build_model(seed)
    model.fit(texts[train], labels[train])
    predicted = model.predict(texts)
    confidence = model.predict_proba(texts).max(axis=1)

    present = [label for label in LABELS if label in set(labels[test]) | set(predicted[test])]
    report_text = classification_report(labels[test], predicted[test], labels=present, digits=2, zero_division=0)
    report_json = classification_report(labels[test], predicted[test], labels=present, output_dict=True, zero_division=0)
    accuracy = accuracy_score(labels[test], predicted[test])

    in_test = np.zeros(len(records), dtype=bool)
    in_test[test] = True
    with conn:
        run_id = conn.execute(
            """
            INSERT INTO classifier_runs (seed, split, n_records, n_train, n_test, accuracy, report_text, report_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (seed, split, len(records), len(train), len(test), float(accuracy), report_text, json.dumps(report_json)),
        ).lastrowid
        conn.executemany(
            "INSERT INTO predictions (run_id, annotation_id, predicted, confidence, in_test) VALUES (?, ?, ?, ?, ?)",
            [(run_id, r.id, str(p), float(c), int(t)) for r, p, c, t in zip(records, predicted, confidence, in_test)],
        )
    return run_id


def latest_run(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM classifier_runs ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    run = dict(row)
    run["report"] = json.loads(run.pop("report_json"))
    run["predictions"] = {
        p["annotation_id"]: {"predicted": p["predicted"], "confidence": p["confidence"], "in_test": bool(p["in_test"])}
        for p in conn.execute("SELECT * FROM predictions WHERE run_id = ?", (run["id"],))
    }
    return run


def run_history(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT id, created_at, seed, split, n_records, n_train, n_test, accuracy FROM classifier_runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    return [dict(r) for r in rows]
