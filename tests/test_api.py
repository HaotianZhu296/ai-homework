import base64
import json
from pathlib import Path

import pytest

import handler
from resume_text import UnsupportedFile, extract_text
from scoring import parse_assessment, score_candidate

ROOT = Path(__file__).resolve().parent.parent
JOBS = {j["job_id"]: j for j in json.loads((ROOT / "seed" / "job_requirements.json").read_text())}
ALEX = ROOT / "data" / "resumes" / "hw0-09_alex_carter_resume.docx"
JOHN = ROOT / "data" / "resumes" / "hw0-09_john_smith_resume.docx"


class FakeTable:
    def __init__(self, items=None, key=("job_id",)):
        self.items = {tuple(i[k] for k in key): i for i in (items or [])}
        self.key = key

    def get_item(self, Key):
        item = self.items.get(tuple(Key[k] for k in self.key))
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[tuple(Item[k] for k in self.key)] = Item

    def scan(self):
        return {"Items": list(self.items.values())}

    def query(self, KeyConditionExpression):
        job_id = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [i for i in self.items.values() if i["job_id"] == job_id]}


@pytest.fixture
def api(monkeypatch):
    jobs = FakeTable(JOBS.values())
    candidates = FakeTable(key=("job_id", "candidate_email"))
    monkeypatch.setattr(handler, "tables", lambda: (jobs, candidates))
    return jobs, candidates


def call(method, path, body=None, headers=None, b64=False):
    event = {"httpMethod": method, "path": path, "headers": headers or {}, "body": body, "isBase64Encoded": b64}
    resp = handler.handler(event, None)
    return resp["statusCode"], json.loads(resp["body"])


def assessment(statuses: dict, **extra) -> str:
    return json.dumps({"assessments": [{"id": k, "status": v, "evidence": "x"} for k, v in statuses.items()], **extra})


# ---------- resume text ----------

def test_docx_extraction_keeps_sections_and_bullets():
    text, kind = extract_text(ALEX.read_bytes(), ALEX.name)
    assert kind == "docx"
    assert "7+ years of experience" in text
    assert "- Python, JavaScript" in text
    assert "Graduated: 2024" in text


def test_unsupported_and_empty_files_are_rejected():
    with pytest.raises(UnsupportedFile):
        extract_text(b"", "x.docx")
    with pytest.raises(UnsupportedFile):
        extract_text(b"PK\x03\x04 not really a zip", "resume.docx")


def test_parse_endpoint_accepts_multipart_upload(api):
    boundary = "----zapier"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{JOHN.name}\"\r\n"
        "Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n"
    ).encode() + JOHN.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    status, data = call(
        "POST",
        "/resumes/parse",
        base64.b64encode(body).decode(),
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        b64=True,
    )
    assert status == 200 and data["kind"] == "docx"
    assert "early childhood development" in data["resume_text"]


def test_parse_endpoint_accepts_base64_json_and_rejects_empty(api):
    payload = json.dumps({"filename": ALEX.name, "content_base64": base64.b64encode(ALEX.read_bytes()).decode()})
    status, data = call("POST", "/resumes/parse", payload, {"Content-Type": "application/json"})
    assert status == 200 and data["characters"] > 1000
    status, _ = call("POST", "/resumes/parse", "{}", {"Content-Type": "application/json"})
    assert status == 400


def test_drive_links_become_direct_downloads():
    assert handler.drive_download_url("https://drive.google.com/open?id=abc_123") == (
        "https://drive.google.com/uc?export=download&id=abc_123"
    )
    assert handler.drive_download_url("https://drive.google.com/file/d/XYZ-9/view?usp=sharing").endswith("id=XYZ-9")


# ---------- jobs ----------

def test_job_lookup_by_id_or_title(api):
    status, data = call("GET", "/jobs/Software%20Engineer")
    assert status == 200 and data["job_id"] == "software-engineer"
    assert "1. [experience] (MANDATORY, weight 25)" in data["requirements_text"]
    assert call("GET", "/jobs/ai-engineer")[0] == 200
    assert call("GET", "/jobs/chef")[0] == 404
    status, data = call("GET", "/jobs")
    assert [j["job_id"] for j in data["jobs"]] == ["ai-engineer", "software-engineer"]


def test_seed_data_is_valid():
    from seed_jobs import validate

    for job in JOBS.values():
        assert validate(job) == []


# ---------- scoring ----------

def test_missing_mandatory_requirement_always_rejects():
    job = JOBS["software-engineer"]
    statuses = {r["id"]: "met" for r in job["requirements"]}
    statuses["experience"] = "partial"
    result = score_candidate(job, parse_assessment(assessment(statuses)))
    assert result["score"] == 88  # 100 - 25 * 0.5, rounded
    assert result["decision"] == "reject" and result["missing_mandatory"] == ["experience"]


def test_threshold_decides_when_mandatory_is_met():
    job = JOBS["software-engineer"]
    low = {"experience": "met", "languages": "partial"}  # 25 + 7.5 = 32.5
    assert score_candidate(job, parse_assessment(assessment(low)))["decision"] == "reject"
    high = {"experience": "met", "degree": "met", "languages": "met", "sql": "met"}  # 70
    result = score_candidate(job, parse_assessment(assessment(high)))
    assert (result["score"], result["decision"]) == (70, "advance")


def test_assessment_parsing_is_tolerant_of_fences_and_unknown_status():
    raw = "Here you go:\n```json\n" + assessment({"experience": "Met", "sql": "maybe"}) + "\n```"
    result = score_candidate(JOBS["software-engineer"], parse_assessment(raw))
    rows = {r["id"]: r["status"] for r in result["requirements"]}
    assert rows["experience"] == "met" and rows["sql"] == "not_met" and rows["git"] == "not_met"


# ---------- evaluations and ranking ----------

def test_evaluations_are_stored_and_ranked(api):
    sw = JOBS["software-engineer"]
    strong = assessment({r["id"]: "met" for r in sw["requirements"]}, summary="Strong fit.")
    weak = assessment({"communication": "met"}, red_flags=["unrelated field"])
    for name, email, a in [("Alex Carter", "alex@example.com", strong), ("John Smith", "john@example.com", weak)]:
        status, data = call(
            "POST",
            "/evaluations",
            json.dumps({"job": "Software Engineer", "candidate_name": name, "candidate_email": email, "assessment": a}),
            {"Content-Type": "application/json"},
        )
        assert status == 201
    assert data["decision"] == "reject" and data["rank"] == 2 and data["candidates_for_job"] == 2

    status, ranking = call("GET", "/rankings/software-engineer")
    assert [(c["rank"], c["candidate_name"], c["decision"]) for c in ranking["candidates"]] == [
        (1, "Alex Carter", "advance"),
        (2, "John Smith", "reject"),
    ]


def test_evaluation_validation_errors(api):
    headers = {"Content-Type": "application/json"}
    assert call("POST", "/evaluations", json.dumps({"job": "software-engineer"}), headers)[0] == 400
    bad = json.dumps({"job": "software-engineer", "candidate_email": "a@b.c", "assessment": "not json"})
    assert call("POST", "/evaluations", bad, headers)[0] == 422
    assert call("DELETE", "/jobs")[0] == 404
