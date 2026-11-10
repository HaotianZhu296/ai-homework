"""Run each solution in the eval dataset against unit tests.

This is an independent check of the LLM judge, not part of the judge itself:
the judge never sees these tests. Each snippet runs in its own isolated Python
subprocess with a time limit.

    python exec_check.py                       # checks data/eval_dataset.jsonl
    python exec_check.py --field ideal         # check the reference solutions only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "data" / "test_cases.json"

HARNESS = r"""
import json, sys
spec = json.loads(sys.stdin.read())
namespace = {}
try:
    exec(spec["code"], namespace)
    fn = namespace[spec["function"]]
except Exception as exc:
    print(json.dumps({"error": f"{type(exc).__name__}: {exc}", "results": []}))
    sys.exit(0)
results = []
for args, expected in spec["cases"]:
    try:
        got = fn(*args)
        results.append({"args": args, "expected": expected, "got": got, "passed": got == expected})
    except Exception as exc:
        results.append({"args": args, "expected": expected, "got": f"{type(exc).__name__}: {exc}", "passed": False})
print(json.dumps({"error": None, "results": results}, default=repr))
"""


def run_tests(code: str, function: str, cases: list, timeout: float = 5.0) -> dict:
    spec = json.dumps({"code": code, "function": function, "cases": cases})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", HARNESS],
            input=spec,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        out = {"error": "timeout", "results": []}
    except json.JSONDecodeError:
        out = {"error": f"harness failed: {proc.stderr.strip()[-300:]}", "results": []}
    passed = sum(r["passed"] for r in out["results"])
    return {**out, "passed": passed, "total": len(cases)}


def check_dataset(dataset: Path, field: str = "sampled") -> list[dict]:
    tests = json.loads(TESTS.read_text())
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    report = []
    for row in rows:
        spec = tests[row["input"]]
        report.append({"input": row["input"], **run_tests(row[field], spec["function"], spec["cases"])})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "eval_dataset.jsonl")
    parser.add_argument("--field", choices=["ideal", "sampled", "both"], default="both")
    args = parser.parse_args()
    fields = ["ideal", "sampled"] if args.field == "both" else [args.field]
    for field in fields:
        print(f"== {field}")
        for r in check_dataset(args.dataset, field):
            fails = [f"{x['args']} -> {x['got']!r} (expected {x['expected']!r})" for x in r["results"] if not x["passed"]]
            print(f"  {r['passed']}/{r['total']}  {r['input']}" + (f"\n      {r['error']}" if r["error"] else ""))
            for f in fails:
                print(f"      fail: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
