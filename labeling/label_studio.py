"""Set up the Label Studio project, and export its annotations.

Start Label Studio first (see README), then:

    python labeling/label_studio.py setup     # create the project and import hw0-07_inputs.csv
    # ... label every task in the Label Studio UI ...
    python labeling/label_studio.py export    # save the annotations to data/label_studio_export.json

The server URL and API token come from LABEL_STUDIO_URL (default
http://127.0.0.1:8089) and LABEL_STUDIO_API_KEY.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "labeling" / "label_config.xml"
INPUTS = ROOT / "data" / "hw0-07_inputs.csv"
EXPORT = ROOT / "data" / "label_studio_export.json"
PROJECT_TITLE = "hw0-7 reference solutions"


class LabelStudio:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        if token.count(".") == 2:
            # Personal access token (a JWT refresh token, the default since Label Studio 1.15):
            # exchange it for a short-lived access token.
            resp = requests.post(f"{self.url}/api/token/refresh", json={"refresh": token}, timeout=30)
            resp.raise_for_status()
            self.session.headers["Authorization"] = f"Bearer {resp.json()['access']}"
        else:
            self.session.headers["Authorization"] = f"Token {token}"  # legacy token

    def call(self, method: str, path: str, **kw):
        resp = self.session.request(method, f"{self.url}{path}", timeout=30, **kw)
        if resp.status_code >= 400:
            raise RuntimeError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.content else None

    def find_project(self, title: str) -> dict | None:
        data = self.call("GET", "/api/projects", params={"page_size": 100})
        projects = data["results"] if isinstance(data, dict) else data
        return next((p for p in projects if p["title"] == title), None)


def client() -> LabelStudio:
    token = os.environ.get("LABEL_STUDIO_API_KEY")
    if not token:
        sys.exit("Set LABEL_STUDIO_API_KEY to your Label Studio API token.")
    return LabelStudio(os.environ.get("LABEL_STUDIO_URL", "http://127.0.0.1:8089"), token)


def read_inputs() -> list[str]:
    with open(INPUTS, newline="", encoding="utf-8") as f:
        return [row["input"].strip() for row in csv.DictReader(f)]


def setup(ls: LabelStudio) -> None:
    project = ls.find_project(PROJECT_TITLE)
    if project is None:
        project = ls.call(
            "POST",
            "/api/projects",
            json={
                "title": PROJECT_TITLE,
                "description": "Write a reference solution for each programming task in hw0-07_inputs.csv.",
                "label_config": CONFIG.read_text(),
            },
        )
        print(f"created project {project['id']}")
    else:
        ls.call("PATCH", f"/api/projects/{project['id']}", json={"label_config": CONFIG.read_text()})
        print(f"project {project['id']} already exists; label config updated")

    existing = {t["data"]["input"] for t in list_tasks(ls, project["id"])}
    new = [{"data": {"row": i, "input": text}} for i, text in enumerate(read_inputs()) if text not in existing]
    if new:
        ls.call("POST", f"/api/projects/{project['id']}/import", json=new)
    print(f"imported {len(new)} new tasks ({len(existing) + len(new)} total)")
    print(f"label them at {ls.url}/projects/{project['id']}/data")


def list_tasks(ls: LabelStudio, project_id: int) -> list[dict]:
    data = ls.call("GET", "/api/tasks", params={"project": project_id, "page_size": 1000})
    return data["tasks"] if isinstance(data, dict) else data


def export(ls: LabelStudio) -> None:
    project = ls.find_project(PROJECT_TITLE)
    if project is None:
        sys.exit("Project not found. Run `setup` first.")
    tasks = ls.call("GET", f"/api/projects/{project['id']}/export", params={"exportType": "JSON"})
    unlabeled = [t["data"]["input"] for t in tasks if not any(not a.get("was_cancelled") for a in t["annotations"])]
    EXPORT.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n")
    print(f"exported {len(tasks)} tasks -> {EXPORT.relative_to(ROOT)}")
    if unlabeled:
        print(f"warning: {len(unlabeled)} task(s) have no annotation yet: {unlabeled}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["setup", "export"])
    args = parser.parse_args()
    {"setup": setup, "export": export}[args.command](client())


if __name__ == "__main__":
    main()
