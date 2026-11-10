"""Run the weather prompt on a set of locations and check every reply.

For each input, the assistant gets prompt.md as its system prompt and a single
``http_get`` tool (http_tool_server.py). Its reply is validated against the
output rules and compared field by field with reference.py, which runs the
same procedure in plain Python right after.

    python part1_weather/run_weather.py                  # default inputs
    python part1_weather/run_weather.py "Austin, TX"     # your own inputs
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from llm import DEFAULT_MODEL, run_prompt  # noqa: E402
from reference import reference_forecast, validate_output  # noqa: E402

DEFAULT_INPUTS = [
    "47.6062,-122.3321",                          # the example point from the assignment
    "Boston, MA",                                 # city name, needs geocoding
    "Denver",                                     # city without a state
    "1600 Pennsylvania Ave NW, Washington, DC",   # street address
    "Chicago, IL | tuesday night",                # a specific forecast period, any case
    "Chicago, IL | Wednesday",                    # a weekday NOAA may rename for a holiday
    "Paris, France",                              # outside NOAA coverage -> error output
    "Chicago, IL | Someday",                      # unknown period -> error output
]
TOOL_NAME = "mcp__noaa__http_get"


def mcp_config() -> dict:
    return {
        "mcpServers": {
            "noaa": {
                "command": sys.executable,
                "args": [str(HERE / "http_tool_server.py")],
            }
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", default=DEFAULT_INPUTS)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", type=Path, default=HERE / "results" / "weather_runs.json")
    args = parser.parse_args()

    system_prompt = (HERE / "prompt.md").read_text()
    runs = []
    for user_input in args.inputs:
        print(f"> {user_input}", flush=True)
        result = run_prompt(
            system_prompt,
            user_input,
            model=args.model,
            mcp_config=mcp_config(),
            allowed_tools=[TOOL_NAME],
        )
        parsed, problems = validate_output(result.text)
        expected = reference_forecast(user_input)
        mismatches = (
            {k: {"assistant": parsed.get(k), "reference": v} for k, v in expected.items() if parsed.get(k) != v}
            if parsed is not None
            else {}
        )
        ok = not problems and parsed is not None and not mismatches
        print(f"  {result.text}")
        print(f"  {'PASS' if ok else 'FAIL'}  format problems={problems or 'none'}  mismatches={mismatches or 'none'}")
        runs.append(
            {
                "input": user_input,
                "reply": result.text,
                "valid_format": not problems and parsed is not None,
                "format_problems": problems,
                "reference": expected,
                "matches_reference": parsed is not None and not mismatches,
                "mismatches": mismatches,
                "turns": result.num_turns,
                "cost_usd": round(result.cost_usd, 4),
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "model": args.model,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "passed": sum(r["valid_format"] and r["matches_reference"] for r in runs),
        "total": len(runs),
        "runs": runs,
    }
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"\n{summary['passed']}/{summary['total']} passed -> {args.out}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
