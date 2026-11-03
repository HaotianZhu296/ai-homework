"""Load multi_annotator_dataset_list.csv into SQLite.

Expected columns: id, text, annotations — where annotations is a JSON list of three labels,
e.g. ["negative", "negative", "positive"].

    python import_data.py                              # data/multi_annotator_dataset_list.csv
    python import_data.py --csv path/to/file.csv --db annotations.db

Importing is idempotent: rows whose id already exists are left untouched (annotations are
immutable), so the script can safely be re-run.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from db import BASE_DIR, DB_PATH, LABELS, connect, sentence_id

DATA_DIR = BASE_DIR / "data"
OFFICIAL_CSV = DATA_DIR / "multi_annotator_dataset_list.csv"
SAMPLE_CSV = DATA_DIR / "sample_multi_annotator_dataset.csv"


@dataclass
class ImportResult:
    path: Path
    inserted: int = 0
    existing: int = 0
    skipped: list[str] = field(default_factory=list)


def parse_annotations(raw: str) -> list[str]:
    raw = (raw or "").strip()
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        # Tolerate "a, b, c" / "a|b|c" as well as JSON.
        values = [v for v in raw.replace("|", ",").split(",") if v.strip()]
    if not isinstance(values, list):
        raise ValueError("annotations must be a list")
    labels = [str(v).strip().strip("'\"").lower() for v in values]
    if len(labels) != 3:
        raise ValueError(f"expected 3 annotations, got {len(labels)}")
    bad = [label for label in labels if label not in LABELS]
    if bad:
        raise ValueError(f"unknown label(s) {bad}")
    return labels


def import_csv(conn: sqlite3.Connection, csv_path: Path) -> ImportResult:
    result = ImportResult(csv_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"id", "text", "annotations"} - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{csv_path} is missing column(s): {', '.join(sorted(missing))}")
        with conn:
            for line, row in enumerate(reader, start=2):
                try:
                    record_id = int(row["id"])
                    text = " ".join((row["text"] or "").split())
                    if not text:
                        raise ValueError("empty text")
                    labels = parse_annotations(row["annotations"])
                except ValueError as err:
                    result.skipped.append(f"line {line}: {err}")
                    continue
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO annotations
                        (id, sentence_id, text, annotator_1, annotator_2, annotator_3, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'dataset')
                    """,
                    (record_id, sentence_id(conn, text), text, *labels),
                )
                if cursor.rowcount:
                    result.inserted += 1
                else:
                    result.existing += 1
    return result


def default_csv() -> Path | None:
    """The official dataset if present, otherwise the bundled synthetic sample."""
    for path in (OFFICIAL_CSV, SAMPLE_CSV):
        if path.exists():
            return path
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a multi-annotator CSV into SQLite.")
    parser.add_argument("--csv", type=Path, default=None, help="CSV file (default: data/multi_annotator_dataset_list.csv)")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database file")
    args = parser.parse_args()

    csv_path = args.csv or default_csv()
    if csv_path is None or not csv_path.exists():
        raise SystemExit(f"CSV file not found. Put the dataset at {OFFICIAL_CSV} or pass --csv.")
    if csv_path == SAMPLE_CSV:
        print(f"Note: {OFFICIAL_CSV.name} not found, importing the synthetic sample instead.")

    conn = connect(args.db)
    result = import_csv(conn, csv_path)
    print(f"Imported {result.inserted} new rows from {csv_path.name} into {args.db} "
          f"({result.existing} already present, {len(result.skipped)} skipped).")
    for problem in result.skipped[:20]:
        print(f"  skipped {problem}")


if __name__ == "__main__":
    main()
