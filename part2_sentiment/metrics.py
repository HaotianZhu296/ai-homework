"""Load the multi-annotator CSV, parse model replies and score predictions."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

LABELS = ["positive", "negative", "neutral", "sarcastic"]


def load_dataset(path: Path) -> list[dict]:
    """Rows of {id, text, annotations: [label, label, label]}, labels lowercased."""
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            labels = [str(x).strip().lower() for x in json.loads(row["annotations"])]
            if row["text"].strip() and labels and all(l in LABELS for l in labels):
                records.append({"id": row["id"], "text": row["text"].strip(), "annotations": labels})
    return records


def parse_label(reply: str) -> tuple[str | None, str | None, str | None]:
    """Return (label, rationale, error) from a model reply."""
    try:
        data = json.loads(reply)
    except json.JSONDecodeError as exc:
        return None, None, f"not valid JSON: {exc}"
    if not isinstance(data, dict):
        return None, None, "reply is not a JSON object"
    label = data.get("label")
    if label not in LABELS:
        return None, data.get("rationale"), f"invalid label: {label!r}"
    return label, data.get("rationale"), None


def majority(votes: Counter, fallback: Counter | None = None) -> str:
    """Most common label. Ties go to the label most common in `fallback`, then to LABELS order."""
    top = max(votes.values())
    tied = [l for l in LABELS if votes.get(l, 0) == top]
    if len(tied) > 1 and fallback:
        best = max(fallback.get(l, 0) for l in tied)
        tied = [l for l in tied if fallback.get(l, 0) == best]
    return tied[0]


def score(records: list[dict], predictions: dict[str, str | None]) -> dict:
    pooled: dict[str, Counter] = defaultdict(Counter)
    for r in records:
        pooled[r["text"]].update(r["annotations"])

    # 1. Sentence level: each distinct sentence, gold = majority of all its votes.
    per_sentence = {}
    for text, votes in pooled.items():
        gold = majority(votes)
        per_sentence[text] = {
            "majority": gold,
            "votes": dict(votes.most_common()),
            "predicted": predictions.get(text),
            "correct": predictions.get(text) == gold,
        }
    sentence_accuracy = sum(v["correct"] for v in per_sentence.values()) / len(per_sentence)

    # 2. Record level: each record, gold = majority of its three votes (ties broken by the pooled votes).
    gold_labels, pred_labels = [], []
    for r in records:
        gold_labels.append(majority(Counter(r["annotations"]), pooled[r["text"]]))
        pred_labels.append(predictions.get(r["text"]))
    record_accuracy = sum(g == p for g, p in zip(gold_labels, pred_labels)) / len(records)

    confusion = {g: {p: 0 for p in LABELS + ["invalid"]} for g in LABELS}
    for g, p in zip(gold_labels, pred_labels):
        confusion[g][p if p in LABELS else "invalid"] += 1

    per_label = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[g][label] for g in LABELS if g != label)
        fn = sum(confusion[label].values()) - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3), "support": tp + fn}
    macro_f1 = sum(v["f1"] for v in per_label.values()) / len(LABELS)

    # 3. Vote level: how often the model agrees with a single annotator, compared with
    #    how often two annotators on the same record agree with each other.
    votes_total = sum(len(r["annotations"]) for r in records)
    vote_agreement = sum(
        sum(a == predictions.get(r["text"]) for a in r["annotations"]) for r in records
    ) / votes_total
    pairs = [(a, b) for r in records for a, b in combinations(r["annotations"], 2)]
    inter_annotator = sum(a == b for a, b in pairs) / len(pairs)

    return {
        "records": len(records),
        "sentences": len(per_sentence),
        "invalid": sum(p is None for p in predictions.values()),
        "sentence_accuracy": round(sentence_accuracy, 4),
        "record_accuracy": round(record_accuracy, 4),
        "macro_f1": round(macro_f1, 4),
        "vote_agreement": round(vote_agreement, 4),
        "inter_annotator_agreement": round(inter_annotator, 4),
        "per_label": per_label,
        "confusion": confusion,
        "per_sentence": per_sentence,
    }
