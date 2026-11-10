"""Run the model-graded eval described in eval_config.yaml.

Every judge model grades every sample `runs_per_sample` times. The script then
reports, per judge:

- the mean score over all samples, and the variance/std of the per-sample means;
- judge_std: how much the repeated runs on the same sample disagree;
- a bootstrap 95% confidence interval of the mean (resampling samples and runs);
- a sanity check against unit tests the judge never sees (exec_check.py).

    python run_eval.py                          # uses eval_config.yaml
    python run_eval.py --config my_config.yaml
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

from exec_check import check_dataset
from llm import run_prompt

ROOT = Path(__file__).resolve().parent


def parse_score(reply: str, choices: dict[int, str], field: str = "score") -> tuple[int | None, str | None]:
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    score = data.get(field)
    if isinstance(score, bool) or not isinstance(score, int) or score not in choices:
        return None, data.get("reasoning")
    return score, data.get("reasoning")


def judge_once(system_prompt: str, user_message: str, model: str, choices: dict, field: str, retries: int) -> dict:
    attempt = {}
    for i in range(retries + 1):
        result = run_prompt(system_prompt, user_message, model=model, max_turns=1)
        score, reasoning = parse_score(result.text, choices, field)
        attempt = {"score": score, "reasoning": reasoning, "reply": result.text, "attempts": i + 1, "cost_usd": result.cost_usd}
        if score is not None:
            break
    return attempt


def bootstrap_ci(per_sample_runs: list[list[int]], iterations: int, seed: int) -> tuple[float, float]:
    """95% CI of the mean, resampling samples and then runs within each sample."""
    rng = random.Random(seed)
    n = len(per_sample_runs)
    means = []
    for _ in range(iterations):
        picked = [per_sample_runs[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(statistics.fmean(rng.choices(runs, k=len(runs))) for runs in picked))
    means.sort()
    return means[int(0.025 * iterations)], means[int(0.975 * iterations) - 1]


def summarize(samples: list[dict], cfg: dict) -> dict:
    per_sample_runs = [[r["score"] for r in s["runs"] if r["score"] is not None] for s in samples]
    per_sample_means = [statistics.fmean(runs) for runs in per_sample_runs]
    all_scores = [x for runs in per_sample_runs for x in runs]
    lo, hi = bootstrap_ci(per_sample_runs, cfg["bootstrap"]["iterations"], cfg["bootstrap"]["seed"])
    return {
        "mean": round(statistics.fmean(all_scores), 3),
        "variance": round(statistics.pvariance(per_sample_means), 3),
        "std": round(statistics.pstdev(per_sample_means), 3),
        "judge_std": round(statistics.fmean(statistics.pstdev(runs) for runs in per_sample_runs), 3),
        "ci95": [round(lo, 3), round(hi, 3)],
        "score_counts": {str(k): all_scores.count(k) for k in sorted(cfg["grader"]["choices"], reverse=True)},
        "invalid_runs": sum(r["score"] is None for s in samples for r in s["runs"]),
    }


def write_report(path: Path, results: dict, cfg: dict) -> None:
    choices = cfg["grader"]["choices"]
    lines = [
        f"# Eval report: {results['eval']}",
        "",
        f"Run at {results['run_at']} on `{results['dataset']}` "
        f"({results['num_samples']} samples x {results['runs_per_sample']} runs per judge).",
        "",
        "## Summary",
        "",
        "| Judge | Mean score | 95% CI | Variance of sample means | Std | Judge std (repeat runs) | Invalid replies |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, j in results["judges"].items():
        s = j["summary"]
        lines.append(
            f"| `{model}` | {s['mean']:.2f} | [{s['ci95'][0]:.2f}, {s['ci95'][1]:.2f}] | {s['variance']:.3f} "
            f"| {s['std']:.3f} | {s['judge_std']:.3f} | {s['invalid_runs']} |"
        )
    lines += ["", "## Per sample", ""]
    header = "| Task | Unit tests | " + " | ".join(f"`{m}` scores (mean)" for m in results["judges"]) + " |"
    lines += [header, "| --- | --- | " + " | ".join("---" for _ in results["judges"]) + " |"]
    for i, sample in enumerate(results["exec_check"]):
        cells = []
        for model, j in results["judges"].items():
            runs = [r["score"] for r in j["samples"][i]["runs"]]
            cells.append(f"{', '.join(str(x) for x in runs)} ({statistics.fmean(x for x in runs if x is not None):.1f})")
        lines.append(f"| {sample['input']} | {sample['passed']}/{sample['total']} | " + " | ".join(cells) + " |")
    lines += ["", "## Sanity check against unit tests", ""]
    for model, j in results["judges"].items():
        c = j["sanity"]
        lines.append(f"- `{model}`: {c['agree']}/{c['total']} samples agree with the unit tests ({c['rule']}).")
    lines += ["", "## Judge reasoning (first run)", ""]
    for model, j in results["judges"].items():
        lines += [f"### `{model}`", ""]
        for s in j["samples"]:
            r = s["runs"][0]
            label = choices.get(r["score"], "invalid")
            lines.append(f"- **{s['input']}** -> {r['score']} ({label}): {r['reasoning']}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=ROOT / "eval_config.yaml")
    args = parser.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    grader = cfg["grader"]
    choices = {int(k): v for k, v in grader["choices"].items()}
    system_prompt = (ROOT / grader["system_prompt"]).read_text()
    template = (ROOT / grader["user_template"]).read_text()
    dataset = ROOT / cfg["eval"]["dataset"]
    rows = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    runs = cfg["sampling"]["runs_per_sample"]

    exec_results = check_dataset(dataset, "sampled")
    threshold = cfg["sanity_check"]["pass_threshold"]

    results = {
        "eval": cfg["eval"]["name"],
        "dataset": cfg["eval"]["dataset"],
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "num_samples": len(rows),
        "runs_per_sample": runs,
        "exec_check": [{k: r[k] for k in ("input", "passed", "total")} for r in exec_results],
        "judges": {},
    }

    for model in cfg["judges"]:
        jobs = [(i, row) for i, row in enumerate(rows) for _ in range(runs)]

        def work(job):
            _, row = job
            message = template.format(input=row["input"], ideal=row["ideal"], sampled=row["sampled"])
            return judge_once(system_prompt, message, model, choices, grader["score_field"], grader["invalid_retries"])

        with ThreadPoolExecutor(max_workers=cfg["sampling"]["concurrency"]) as pool:
            outcomes = list(pool.map(work, jobs))

        samples = [{"input": row["input"], "runs": []} for row in rows]
        for (i, _), outcome in zip(jobs, outcomes):
            samples[i]["runs"].append(outcome)

        agree = 0
        for sample, ex in zip(samples, exec_results):
            mean = statistics.fmean(r["score"] for r in sample["runs"] if r["score"] is not None)
            all_pass = ex["passed"] == ex["total"]
            agree += (mean >= threshold) == all_pass
        results["judges"][model] = {
            "summary": summarize(samples, cfg),
            "sanity": {
                "agree": agree,
                "total": len(samples),
                "rule": f"all tests pass <=> mean score >= {threshold}",
            },
            "cost_usd": round(sum(o["cost_usd"] for o in outcomes), 4),
            "samples": samples,
        }
        s = results["judges"][model]["summary"]
        print(f"{model}: mean {s['mean']:.2f}, 95% CI {s['ci95']}, variance {s['variance']}, judge std {s['judge_std']}")

    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(exist_ok=True)
    (out_dir / "eval_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    write_report(out_dir / "report.md", results, cfg)
    print(f"-> {out_dir / 'eval_results.json'}\n-> {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
