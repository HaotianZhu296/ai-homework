"""Load (or update) the job requirements in the DynamoDB JobRequirements table.

    python seed/seed_jobs.py                 # table name read from the SmartHireStack outputs
    python seed/seed_jobs.py --table NAME --profile PROFILE --region us-east-2

Each job is validated first: unique requirement ids, positive weights summing
to 100, and at least one mandatory requirement. Editing job_requirements.json
and rerunning this script is how requirements are managed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STACK = "SmartHireStack"


def validate(job: dict) -> list[str]:
    problems = []
    for key in ("job_id", "title", "requirements"):
        if not job.get(key):
            problems.append(f"missing '{key}'")
    reqs = job.get("requirements", [])
    ids = [r.get("id") for r in reqs]
    if len(ids) != len(set(ids)):
        problems.append("requirement ids must be unique")
    if any(not isinstance(r.get("weight"), int) or r["weight"] <= 0 for r in reqs):
        problems.append("every weight must be a positive integer")
    elif sum(r["weight"] for r in reqs) != 100:
        problems.append(f"weights sum to {sum(r['weight'] for r in reqs)}, expected 100")
    if not any(r.get("mandatory") for r in reqs):
        problems.append("at least one requirement must be mandatory")
    return problems


def stack_output(session, key: str) -> str:
    outputs = session.client("cloudformation").describe_stacks(StackName=STACK)["Stacks"][0]["Outputs"]
    return next(o["OutputValue"] for o in outputs if o["OutputKey"] == key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=HERE / "job_requirements.json")
    parser.add_argument("--table")
    parser.add_argument("--profile")
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args()

    jobs = json.loads(args.data.read_text())
    for job in jobs:
        problems = validate(job)
        if problems:
            print(f"{job.get('job_id', '?')}: " + "; ".join(problems), file=sys.stderr)
            return 1

    import boto3

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    table_name = args.table or stack_output(session, "JobsTableName")
    table = session.resource("dynamodb").Table(table_name)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for job in jobs:
        table.put_item(Item={**job, "updated_at": now})
        print(f"saved {job['job_id']} ({len(job['requirements'])} requirements) -> {table_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
