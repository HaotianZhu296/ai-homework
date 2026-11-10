"""Classify the multi-annotator dataset with the prompt in prompt.md and score it.

Each distinct sentence is sent to the model once (prompt.md is the system prompt
and the sentence is the user message). The predictions are then scored against
the human annotations in three ways; see metrics.py.

    python part2_sentiment/run_sentiment.py
    python part2_sentiment/run_sentiment.py --model claude-haiku-5-5
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from llm import DEFAULT_MODEL, run_prompt  # noqa: E402
from metrics import LABELS, load_dataset, parse_label, score  # noqa: E402

OFFICIAL = HERE / "data" / "hw0-3_multi_annotator_dataset_list.csv"
SAMPLE = HERE / "data" / "sample_multi_annotator_dataset.csv"


def classify(system_prompt: str, sentence: str, model: str, retries: int = 1) -> dict:
    last = {}
    for _ in range(retries + 1):
        result = run_prompt(system_prompt, f"Sentence: {sentence}", model=model, max_turns=1)
        label, rationale, error = parse_label(result.text)
        last = {"reply": result.text, "label": label, "rationale": rationale, "error": error, "cost_usd": result.cost_usd}
        if label is not None:
            break
    return last


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=OFFICIAL if OFFICIAL.exists() else SAMPLE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    records = load_dataset(args.data)
    sentences = sorted({r["text"] for r in records})
    system_prompt = (HERE / "prompt.md").read_text()
    print(f"{len(records)} records, {len(sentences)} distinct sentences, model {args.model}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        outputs = dict(zip(sentences, pool.map(lambda s: classify(system_prompt, s, args.model), sentences)))

    predictions = {s: o["label"] for s, o in outputs.items()}
    metrics = score(records, predictions)

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    report = {
        "model": args.model,
        "dataset": args.data.name,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cost_usd": round(sum(o["cost_usd"] for o in outputs.values()), 4),
        "metrics": metrics,
        "predictions": [
            {"text": s, **{k: outputs[s][k] for k in ("label", "rationale", "error")}} for s in sentences
        ],
    }
    out = out_dir / f"sentiment_{args.model}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    for s in sentences:
        gold = metrics["per_sentence"][s]["majority"]
        mark = "  " if predictions[s] == gold else "✗ "
        print(f"{mark}{predictions[s] or 'INVALID':10} gold={gold:10} {s}")
    print(
        f"\nsentence accuracy {metrics['sentence_accuracy']:.1%} | record accuracy {metrics['record_accuracy']:.1%} "
        f"| macro-F1 {metrics['macro_f1']:.3f} | vote agreement {metrics['vote_agreement']:.1%} "
        f"(annotators with each other: {metrics['inter_annotator_agreement']:.1%}) | invalid replies {metrics['invalid']}"
    )
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
