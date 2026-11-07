"""Create the `movies` index mapping and bulk-load the sample movies.

Usage:
    python seed/seed_index.py                       # endpoint from the CDK stack output
    python seed/seed_index.py --endpoint https://search-xxx.us-east-2.es.amazonaws.com
    python seed/seed_index.py --recreate            # drop and rebuild the index

Requests are signed with SigV4 using your local AWS credentials
(`--profile` / AWS_PROFILE, `--region` / AWS_REGION).
"""

import argparse
import json
import sys
from pathlib import Path

import boto3
import requests
from requests_aws4auth import AWS4Auth

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "sample-movies.bulk"
MAPPING_FILE = Path(__file__).resolve().parent / "movies_index.json"
INDEX_NAME = "movies"
STACK_NAME = "MovieSearchStack"
DROP_FIELDS = ("type",)  # "type": "add" is a leftover from the old bulk format


def load_mapping():
    return json.loads(MAPPING_FILE.read_text())


def prepare_bulk_body(text, index=INDEX_NAME):
    """Validate the bulk file and return (ndjson_body, doc_count).

    Each movie is an action line followed by a document line. Every line is
    parsed (so malformed JSON fails fast), the target index is forced to
    `index`, legacy fields are dropped, and the body always ends with the
    newline the bulk API requires.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) % 2:
        raise ValueError(f"bulk file has an odd number of lines ({len(lines)})")

    out = []
    for i in range(0, len(lines), 2):
        try:
            action = json.loads(lines[i])
            doc = json.loads(lines[i + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON near line {i + 1}: {exc}") from exc
        if set(action) != {"index"}:
            raise ValueError(f"line {i + 1}: expected an 'index' action, got {list(action)}")
        meta = action["index"]
        meta["_index"] = index
        meta.setdefault("_id", doc.get("id"))
        for field in DROP_FIELDS:
            doc.pop(field, None)
        out.append(json.dumps(action, ensure_ascii=False))
        out.append(json.dumps(doc, ensure_ascii=False))

    if not out:
        raise ValueError("bulk file contains no documents")
    return "\n".join(out) + "\n", len(out) // 2


def endpoint_from_stack(session, stack_name=STACK_NAME):
    cfn = session.client("cloudformation")
    stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
    for output in stack.get("Outputs", []):
        if output["OutputKey"] == "OpenSearchEndpoint":
            return output["OutputValue"]
    raise RuntimeError(f"stack {stack_name} has no OpenSearchEndpoint output")


def check(resp, what):
    if resp.status_code >= 300:
        sys.exit(f"{what} failed: HTTP {resp.status_code}\n{resp.text[:1000]}")
    return resp.json()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", help="OpenSearch endpoint (default: MovieSearchStack output)")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="bulk file to load")
    parser.add_argument("--profile", help="AWS profile")
    parser.add_argument("--region", help="AWS region")
    parser.add_argument("--recreate", action="store_true", help="delete the index first if it exists")
    args = parser.parse_args(argv)

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    region = session.region_name
    if not region:
        sys.exit("No AWS region configured; pass --region.")
    endpoint = (args.endpoint or endpoint_from_stack(session)).rstrip("/")
    if not endpoint.startswith("http"):
        endpoint = "https://" + endpoint

    auth = AWS4Auth(region=region, service="es", refreshable_credentials=session.get_credentials())
    http = requests.Session()
    http.auth = auth
    index_url = f"{endpoint}/{INDEX_NAME}"
    print(f"Endpoint: {endpoint}")

    exists = http.head(index_url, timeout=30).status_code == 200
    if exists and args.recreate:
        check(http.delete(index_url, timeout=30), "Deleting index")
        print(f"Deleted existing index '{INDEX_NAME}'")
        exists = False

    if exists:
        print(f"Index '{INDEX_NAME}' already exists; keeping its mapping (use --recreate to rebuild)")
    else:
        check(http.put(index_url, json=load_mapping(), timeout=30), "Creating index")
        print(f"Created index '{INDEX_NAME}' with explicit mapping")

    body, count = prepare_bulk_body(args.data.read_text(encoding="utf-8"))
    print(f"Bulk loading {count} movies from {args.data.name} ({len(body.encode()) / 1024:.0f} KB)")
    result = check(
        http.post(
            f"{endpoint}/_bulk?refresh=true",
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/x-ndjson"},
            timeout=120,
        ),
        "Bulk load",
    )
    if result.get("errors"):
        failed = [item["index"] for item in result["items"] if item["index"].get("error")]
        for item in failed[:5]:
            print(f"  {item['_id']}: {item['error']}")
        sys.exit(f"{len(failed)} of {count} documents failed")

    total = check(http.get(f"{index_url}/_count", timeout=30), "Counting documents")["count"]
    print(f"Done: index '{INDEX_NAME}' now holds {total} movies")


if __name__ == "__main__":
    main()
