"""Multi-annotator sentiment workflow: annotate, store immutably, review agreement, train a classifier."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

import analysis
from db import DB_PATH, LABELS, connect
from import_data import default_csv, import_csv

STATIC_DIR = Path(__file__).resolve().parent / "static"
log = logging.getLogger("annotator")
logging.basicConfig(level=logging.INFO)


def bootstrap(db_path: Path | str) -> None:
    """First start: import the dataset and train an initial classifier."""
    conn = connect(db_path)
    try:
        if conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0:
            csv_path = default_csv()
            if csv_path:
                result = import_csv(conn, csv_path)
                log.info("Imported %d rows from %s", result.inserted, csv_path.name)
        if analysis.latest_run(conn) is None:
            try:
                analysis.train_and_store(conn, seed=42)
            except analysis.ClassifierError as err:
                log.info("Classifier not trained yet: %s", err)
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_path = getattr(app.state, "db_path", DB_PATH)
    bootstrap(app.state.db_path)
    yield


app = FastAPI(title="Multi-Annotator Sentiment", lifespan=lifespan)


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


def record_payload(record: analysis.Record) -> dict:
    return {
        "id": record.id,
        "text": record.text,
        "annotations": record.votes,
        "resolved": record.resolved,
        "agreement": record.agreement,
        "source": record.source,
        "created_at": record.created_at,
    }


# ---- annotating -----------------------------------------------------------------------------

@app.get("/api/labels")
def labels():
    return {"labels": list(LABELS), "annotators": 3}


@app.get("/api/sentence/random")
def random_sentence(exclude: int | None = Query(None), conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute(
        "SELECT id, text FROM sentences WHERE id IS NOT ? ORDER BY RANDOM() LIMIT 1", (exclude,)
    ).fetchone() or conn.execute("SELECT id, text FROM sentences ORDER BY RANDOM() LIMIT 1").fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="No sentences loaded. Run import_data.py first.")
    count = conn.execute("SELECT COUNT(*) FROM annotations WHERE sentence_id = ?", (row["id"],)).fetchone()[0]
    return {"id": row["id"], "text": row["text"], "times_annotated": count}


class AnnotationIn(BaseModel):
    sentence_id: int
    labels: list[str]
    client_key: str | None = None

    @field_validator("labels")
    @classmethod
    def _three_valid_labels(cls, value: list[str]) -> list[str]:
        value = [v.strip().lower() for v in value]
        if len(value) != 3:
            raise ValueError("All three annotators must choose a label.")
        bad = [v for v in value if v not in LABELS]
        if bad:
            raise ValueError(f"Unknown label(s): {', '.join(bad)}")
        return value

    @field_validator("client_key")
    @classmethod
    def _key(cls, value: str | None) -> str | None:
        if value is not None and not (1 <= len(value) <= 64):
            raise ValueError("client_key must be 1-64 characters.")
        return value


@app.post("/api/annotations", status_code=201)
def save_annotation(body: AnnotationIn, conn: sqlite3.Connection = Depends(get_conn)):
    sentence = conn.execute("SELECT id, text FROM sentences WHERE id = ?", (body.sentence_id,)).fetchone()
    if sentence is None:
        raise HTTPException(status_code=404, detail="Unknown sentence.")
    if body.client_key:
        existing = conn.execute("SELECT id FROM annotations WHERE client_key = ?", (body.client_key,)).fetchone()
        if existing:
            # The same draw was already saved — annotations can't be changed afterwards.
            raise HTTPException(status_code=409, detail=f"Already saved as record #{existing['id']}; annotations are immutable.")
    with conn:
        record_id = conn.execute(
            """
            INSERT INTO annotations (sentence_id, text, annotator_1, annotator_2, annotator_3, source, client_key)
            VALUES (?, ?, ?, ?, ?, 'ui', ?)
            """,
            (sentence["id"], sentence["text"], *body.labels, body.client_key),
        ).lastrowid
    record = next(r for r in analysis.load_records(conn) if r.id == record_id)
    return record_payload(record)


# ---- stats & classifier ---------------------------------------------------------------------

def classifier_payload(conn: sqlite3.Connection, total_records: int) -> dict | None:
    run = analysis.latest_run(conn)
    if run is None:
        return None
    return {
        "id": run["id"],
        "created_at": run["created_at"],
        "seed": run["seed"],
        "split": run["split"],
        "accuracy": run["accuracy"],
        "n_records": run["n_records"],
        "n_train": run["n_train"],
        "n_test": run["n_test"],
        "new_since_run": total_records - run["n_records"],
        "report_text": run["report_text"],
        "report": run["report"],
        "_predictions": run["predictions"],
    }


@app.get("/api/stats")
def stats(conn: sqlite3.Connection = Depends(get_conn)):
    records = analysis.load_records(conn)
    classifier = classifier_payload(conn, len(records))
    predictions = classifier.pop("_predictions") if classifier else {}
    rows = []
    for record in records:
        row = record_payload(record)
        pred = predictions.get(record.id)
        row["prediction"] = pred["predicted"] if pred else None
        row["confidence"] = pred["confidence"] if pred else None
        row["in_test"] = pred["in_test"] if pred else None
        rows.append(row)
    sentences = analysis.sentence_summary(records)
    distribution = {label: sum(1 for r in records if r.resolved == label) for label in LABELS}
    return {
        "summary": {
            "total_records": len(records),
            "unique_texts": len(sentences),
            "ui_records": sum(1 for r in records if r.source == "ui"),
            "average_agreement": (sum(r.agreement for r in records) / len(records)) if records else None,
            "full_agreement": sum(1 for r in records if r.agreement == 1.0),
            "resolved_distribution": distribution,
            "classifier_accuracy": classifier["accuracy"] if classifier else None,
        },
        "records": rows,
        "sentences": sentences,
        "classifier": classifier,
        "history": analysis.run_history(conn),
    }


class RunIn(BaseModel):
    split: str = "records"
    seed: int | None = None


@app.post("/api/classifier/run")
def rerun_classifier(body: RunIn | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    body = body or RunIn()
    try:
        run_id = analysis.train_and_store(conn, seed=body.seed, split=body.split)
    except analysis.ClassifierError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None
    run = analysis.latest_run(conn)
    return {"id": run_id, "accuracy": run["accuracy"], "seed": run["seed"], "split": run["split"]}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
