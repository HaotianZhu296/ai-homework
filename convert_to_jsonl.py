"""Merge the Label Studio export with the model outputs into an eval JSONL file.

    python convert_to_jsonl.py

Inputs
    data/hw0-07_inputs.csv                  column `input`: the programming tasks
    data/label_studio_export.json           Label Studio JSON export: the reference solutions
    data/hw0-07_inputs_model_output.csv     column `sampled`: the model's answer for each task,
                                            in the same row order as hw0-07_inputs.csv
Output
    data/eval_dataset.jsonl                 one {"input", "ideal", "sampled"} object per line
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def read_column(path: Path, column: str) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if column not in (reader.fieldnames or []):
            raise ValueError(f"{path.name}: expected a '{column}' column, found {reader.fieldnames}")
        return [row[column] for row in reader]


def ideals_from_export(tasks: list[dict]) -> dict[str, str]:
    """Map each task's input text to its reference solution.

    Uses the most recently updated annotation that was not cancelled, and the
    text of its `ideal` TextArea.
    """
    ideals: dict[str, str] = {}
    for task in tasks:
        annotations = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
        if not annotations:
            continue
        latest = max(annotations, key=lambda a: a.get("updated_at") or a.get("created_at") or "")
        texts = [
            "\n".join(r["value"]["text"])
            for r in latest["result"]
            if r.get("from_name") == "ideal" and r.get("type") == "textarea"
        ]
        if texts and texts[0].strip():
            ideals[task["data"]["input"].strip()] = texts[0].strip("\n")
    return ideals


def build_rows(inputs: list[str], ideals: dict[str, str], sampled: list[str]) -> list[dict]:
    if len(inputs) != len(sampled):
        raise ValueError(f"{len(inputs)} inputs but {len(sampled)} model outputs; rows must line up")
    missing = [text for text in inputs if text.strip() not in ideals]
    if missing:
        raise ValueError(f"no reference solution in the Label Studio export for: {missing}")
    return [
        {"input": text.strip(), "ideal": ideals[text.strip()], "sampled": output.strip("\n")}
        for text, output in zip(inputs, sampled)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inputs", type=Path, default=DATA / "hw0-07_inputs.csv")
    parser.add_argument("--export", type=Path, default=DATA / "label_studio_export.json")
    parser.add_argument("--model-output", type=Path, default=DATA / "hw0-07_inputs_model_output.csv")
    parser.add_argument("--out", type=Path, default=DATA / "eval_dataset.jsonl")
    args = parser.parse_args()

    rows = build_rows(
        read_column(args.inputs, "input"),
        ideals_from_export(json.loads(args.export.read_text())),
        read_column(args.model_output, "sampled"),
    )
    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {args.out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
