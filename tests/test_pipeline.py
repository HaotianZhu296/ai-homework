import json
from pathlib import Path

import pytest

from convert_to_jsonl import build_rows, ideals_from_export, read_column
from exec_check import run_tests
from run_eval import bootstrap_ci, parse_score

ROOT = Path(__file__).resolve().parent.parent
CHOICES = {5: "fully correct", 4: "correct, minor issues", 3: "partially correct", 2: "major issues", 1: "incorrect"}


def annotation(text, cancelled=False, updated="2026-11-09T00:00:00Z"):
    return {
        "was_cancelled": cancelled,
        "updated_at": updated,
        "result": [
            {"from_name": "verified", "type": "choices", "value": {"choices": ["Yes, ran it on test inputs"]}},
            {"from_name": "ideal", "type": "textarea", "value": {"text": [text]}},
        ],
    }


def test_ideals_use_latest_non_cancelled_annotation():
    tasks = [
        {
            "data": {"input": "Task A"},
            "annotations": [
                annotation("old", updated="2026-11-01T00:00:00Z"),
                annotation("new", updated="2026-11-02T00:00:00Z"),
                annotation("cancelled", cancelled=True, updated="2026-11-03T00:00:00Z"),
            ],
        },
        {"data": {"input": "Task B"}, "annotations": []},
    ]
    assert ideals_from_export(tasks) == {"Task A": "new"}


def test_build_rows_checks_alignment_and_missing_labels():
    rows = build_rows(["Task A"], {"Task A": "def a(): pass"}, ["def a(): return 1"])
    assert rows == [{"input": "Task A", "ideal": "def a(): pass", "sampled": "def a(): return 1"}]
    with pytest.raises(ValueError, match="line up"):
        build_rows(["Task A", "Task B"], {"Task A": "x", "Task B": "y"}, ["only one"])
    with pytest.raises(ValueError, match="no reference"):
        build_rows(["Task A"], {}, ["x"])


def test_real_files_merge_into_five_rows():
    export = json.loads((ROOT / "data" / "label_studio_export.json").read_text())
    rows = build_rows(
        read_column(ROOT / "data" / "hw0-07_inputs.csv", "input"),
        ideals_from_export(export),
        read_column(ROOT / "data" / "hw0-07_inputs_model_output.csv", "sampled"),
    )
    assert len(rows) == 5
    assert rows[3]["input"] == "Write a Python function to compute factorial."
    assert "range(1, n)" in rows[3]["sampled"]


def test_exec_check_detects_wrong_and_crashing_code():
    cases = [[[0], 1], [[5], 120]]
    good = run_tests("def f(n):\n    return 1 if n == 0 else n * f(n - 1)", "f", cases)
    bad = run_tests("def f(n):\n    r = 1\n    for i in range(1, n):\n        r *= i\n    return r", "f", cases)
    broken = run_tests("def f(n) return n", "f", cases)
    assert (good["passed"], bad["passed"], broken["passed"]) == (2, 1, 0)
    assert broken["error"].startswith("SyntaxError")


def test_parse_score_accepts_only_rubric_values():
    assert parse_score('{"reasoning": "ok", "score": 4}', CHOICES) == (4, "ok")
    assert parse_score('{"reasoning": "x", "score": 6}', CHOICES)[0] is None
    assert parse_score('{"reasoning": "x", "score": "4"}', CHOICES)[0] is None
    assert parse_score("Score: 4", CHOICES)[0] is None


def test_bootstrap_ci_is_tight_when_scores_do_not_vary():
    assert bootstrap_ci([[5, 5], [5, 5]], iterations=200, seed=1) == (5.0, 5.0)
    lo, hi = bootstrap_ci([[5, 5, 5], [1, 1, 1]], iterations=2000, seed=1)
    assert lo < 3 < hi
