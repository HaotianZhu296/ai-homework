import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for sub in ("lambda", "seed", "infra"):
    sys.path.insert(0, str(ROOT / sub))

os.environ.setdefault("OPENSEARCH_ENDPOINT", "search-test.us-east-2.es.amazonaws.com")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-2")
os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")
