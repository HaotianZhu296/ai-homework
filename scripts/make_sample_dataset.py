"""Generate a synthetic stand-in for multi_annotator_dataset_list.csv.

The official course CSV was not available, so this produces a file in the same format
(id, text, annotations as a JSON list of three labels) with 20 short sentences repeated
across 1,000 records. Each sentence has a "true" sentiment and an ambiguity level; each
annotator independently picks the true label or a plausible confusion.

    python scripts/make_sample_dataset.py            # writes data/sample_multi_annotator_dataset.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "sample_multi_annotator_dataset.csv"

# (text, true label, probability an annotator agrees with it, likely confusions)
SENTENCES = [
    ("I absolutely love this phone.", "positive", 0.95, ["neutral"]),
    ("Great job!", "positive", 0.70, ["sarcastic"]),
    ("This made my whole week.", "positive", 0.90, ["sarcastic"]),
    ("Best purchase I've made all year.", "positive", 0.80, ["sarcastic"]),
    ("The service was quick and friendly.", "positive", 0.92, ["neutral"]),
    ("It works as expected.", "neutral", 0.88, ["positive"]),
    ("The package arrived on Tuesday.", "neutral", 0.95, ["positive"]),
    ("This movie was okay, not great.", "neutral", 0.55, ["negative", "positive"]),
    ("It is a phone with a screen.", "neutral", 0.85, ["sarcastic", "negative"]),
    ("Not good at all.", "negative", 0.95, ["neutral"]),
    ("I hate how it performs.", "negative", 0.93, ["neutral"]),
    ("The battery died after one hour.", "negative", 0.90, ["neutral"]),
    ("Worst customer support ever.", "negative", 0.80, ["sarcastic"]),
    ("I want my money back.", "negative", 0.92, ["neutral"]),
    ("Oh sure, best idea ever.", "sarcastic", 0.85, ["positive"]),
    ("Fantastic — if you like disappointment.", "sarcastic", 0.88, ["negative"]),
    ("Perfect, just what I needed... not.", "sarcastic", 0.75, ["negative", "neutral"]),
    ("Wow, that's just unbelievable!", "sarcastic", 0.50, ["positive", "negative"]),
    ("Thanks a lot for breaking it again.", "sarcastic", 0.82, ["negative"]),
    ("Yeah, because waiting two hours is so fun.", "sarcastic", 0.86, ["negative"]),
]


def generate(rows: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    records = []
    for record_id in range(1, rows + 1):
        text, label, p_agree, confusions = rng.choice(SENTENCES)
        votes = [label if rng.random() < p_agree else rng.choice(confusions) for _ in range(3)]
        records.append({"id": record_id, "text": text, "annotations": json.dumps(votes)})
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "text", "annotations"])
        writer.writeheader()
        writer.writerows(generate(args.rows, args.seed))
    print(f"Wrote {args.rows} rows to {args.out}")


if __name__ == "__main__":
    main()
