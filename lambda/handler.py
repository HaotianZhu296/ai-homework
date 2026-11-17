"""SmartHire API: the AWS side of the Zapier workflow.

Routes (all require the API Gateway key in the `x-api-key` header):

    GET  /jobs                      list the roles in the JobRequirements table
    GET  /jobs/{job}                one role's requirements ({job} = id or title)
    POST /resumes/parse             resume file -> plain text
    POST /evaluations               judge assessment -> score, decision, stored in Candidates
    GET  /rankings/{job}            candidates for a role, best first
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default as email_policy
from urllib.parse import parse_qs, unquote, urlparse

from resume_text import UnsupportedFile, extract_text
from emails import build_email
from scoring import InvalidAssessment, parse_assessment, score_candidate

MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
CORS = {"Access-Control-Allow-Origin": "*"}

_dynamodb = None


def tables():
    global _dynamodb
    if _dynamodb is None:
        import boto3

        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb.Table(os.environ["JOBS_TABLE"]), _dynamodb.Table(os.environ["CANDIDATES_TABLE"])


# ---------- helpers ----------

def respond(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS},
        "body": json.dumps(body, ensure_ascii=False, default=_json_default),
    }


def _json_default(value):
    # DynamoDB returns numbers as Decimal.
    return int(value) if value == int(value) else float(value)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unquote(value or "").strip().lower()).strip("-")


def raw_body(event: dict) -> bytes:
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode("utf-8")


def header(event: dict, name: str) -> str:
    for key, value in (event.get("headers") or {}).items():
        if key.lower() == name.lower():
            return value or ""
    return ""


def parse_fields(event: dict) -> tuple[dict, list[dict]]:
    """Return (fields, files) from a JSON, form-encoded or multipart request body."""
    content_type = header(event, "content-type")
    body = raw_body(event)
    if content_type.startswith("multipart/form-data"):
        message = BytesParser(policy=email_policy).parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body
        )
        fields, files = {}, []
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition") or ""
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                files.append({"name": name, "filename": filename, "content_type": part.get_content_type(), "data": payload})
            else:
                fields[name] = payload.decode("utf-8", errors="replace")
        # Zapier's webhook step sends its "Data" pairs as one form-encoded (or JSON) part named "data".
        packed = fields.pop("data", None)
        if packed:
            try:
                extra = json.loads(packed)
            except json.JSONDecodeError:
                extra = {k: v[0] for k, v in parse_qs(packed).items()}
            if isinstance(extra, dict):
                fields = {**extra, **fields}
        return fields, files
    if content_type.startswith("application/x-www-form-urlencoded"):
        return {k: v[0] for k, v in parse_qs(body.decode("utf-8")).items()}, []
    if not body.strip():
        return {}, []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise ValueError("request body must be JSON, form-encoded or multipart/form-data") from None
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data, []


def drive_download_url(url: str) -> str:
    """Turn a Google Drive 'open?id=' / '/file/d/<id>/view' link into a direct download link."""
    parsed = urlparse(url)
    if parsed.hostname not in ("drive.google.com", "docs.google.com"):
        return url
    file_id = parse_qs(parsed.query).get("id", [None])[0]
    if not file_id:
        match = re.search(r"/d/([\w-]+)", parsed.path)
        file_id = match.group(1) if match else None
    return f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else url


def download(url: str) -> tuple[bytes, str, str]:
    url = drive_download_url(url.strip())
    if urlparse(url).scheme != "https":
        raise ValueError("file_url must be an https:// URL")
    request = urllib.request.Request(url, headers={"User-Agent": "smarthire-resume-parser/1.0"})
    with urllib.request.urlopen(request, timeout=20) as resp:
        data = resp.read(MAX_DOWNLOAD_BYTES + 1)
        content_type = resp.headers.get("Content-Type", "")
        disposition = resp.headers.get("Content-Disposition", "")
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("file is larger than 10 MB")
    match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', disposition)
    filename = unquote(match.group(1)) if match else urlparse(url).path.rsplit("/", 1)[-1]
    if content_type.startswith("text/html"):
        raise ValueError("the URL returned a web page, not a file; it may require sign-in")
    return data, filename, content_type


def format_requirements(job: dict) -> str:
    lines = []
    for i, req in enumerate(job["requirements"], 1):
        flag = "MANDATORY" if req.get("mandatory") else "preferred"
        lines.append(f"{i}. [{req['id']}] ({flag}, weight {int(req['weight'])}) {req['text']}")
    return "\n".join(lines)


def get_job(jobs_table, job_ref: str) -> dict | None:
    item = jobs_table.get_item(Key={"job_id": slugify(job_ref)}).get("Item")
    return item


def job_payload(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "title": job["title"],
        "advance_threshold": job.get("advance_threshold", 70),
        "requirements": job["requirements"],
        "requirements_text": format_requirements(job),
        "updated_at": job.get("updated_at"),
    }


JUDGE_PROMPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "judge_prompt.md")


def build_judge_prompt(job: dict, resume_text: str) -> str:
    """Fill judge_prompt.md with the job and the resume, ready to send to the LLM judge."""
    with open(JUDGE_PROMPT, encoding="utf-8") as f:
        template = f.read()
    return (
        template.replace("{{job_title}}", job["title"])
        .replace("{{requirements_text}}", format_requirements(job))
        .replace("{{resume_text}}", resume_text)
    )


# ---------- routes ----------

def list_jobs(event):
    # GET /jobs?title=Software Engineer is the same as GET /jobs/software-engineer.
    title = (event.get("queryStringParameters") or {}).get("title")
    if title:
        return read_job(event, title)
    jobs_table, _ = tables()
    items = jobs_table.scan().get("Items", [])
    return respond(200, {"jobs": [{"job_id": j["job_id"], "title": j["title"]} for j in sorted(items, key=lambda j: j["job_id"])]})


def read_job(event, job):
    jobs_table, _ = tables()
    record = get_job(jobs_table, job)
    if not record:
        return respond(404, {"error": f"unknown job: {unquote(job)}"})
    return respond(200, job_payload(record))


def parse_resume(event):
    fields, files = parse_fields(event)
    if files:
        f = files[0]
        data, filename, content_type = f["data"], f["filename"], f["content_type"]
    elif fields.get("file_url"):
        data, filename, content_type = download(str(fields["file_url"]))
    elif fields.get("content_base64"):
        data = base64.b64decode(fields["content_base64"])
        filename, content_type = str(fields.get("filename", "")), str(fields.get("content_type", ""))
    elif fields.get("text"):
        data, filename, content_type = str(fields["text"]).encode(), "resume.txt", "text/plain"
    else:
        return respond(400, {"error": "send the resume as a multipart file, or as file_url, content_base64 or text"})
    try:
        text, kind = extract_text(data, filename, content_type)
    except UnsupportedFile as exc:
        return respond(422, {"error": str(exc)})
    body = {"filename": filename, "kind": kind, "characters": len(text), "resume_text": text}
    # With a `job` field, the role's requirements are looked up in DynamoDB and returned too,
    # so one Zapier step gives the judge both the resume and the requirements.
    if fields.get("job"):
        jobs_table, _ = tables()
        record = get_job(jobs_table, str(fields["job"]))
        if not record:
            return respond(404, {"error": f"unknown job: {fields['job']}"})
        body["job"] = job_payload(record)
        body["judge_prompt"] = build_judge_prompt(record, text)
    return respond(200, body)


def create_evaluation(event):
    fields, _ = parse_fields(event)
    missing = [k for k in ("job", "candidate_email", "assessment") if not fields.get(k)]
    if missing:
        return respond(400, {"error": f"missing fields: {', '.join(missing)}"})
    jobs_table, candidates_table = tables()
    job = get_job(jobs_table, str(fields["job"]))
    if not job:
        return respond(404, {"error": f"unknown job: {fields['job']}"})
    try:
        assessment = parse_assessment(fields["assessment"])
    except InvalidAssessment as exc:
        return respond(422, {"error": str(exc)})

    result = score_candidate(job, assessment)
    email = str(fields["candidate_email"]).strip().lower()
    name = str(fields.get("candidate_name") or assessment.get("candidate_name") or email).strip()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    candidates_table.put_item(
        Item={
            "job_id": job["job_id"],
            "candidate_email": email,
            "candidate_name": name,
            "score": result["score"],
            "decision": result["decision"],
            "mandatory_met": result["mandatory_met"],
            "decision_reason": result["decision_reason"],
            "summary": str(assessment.get("summary", ""))[:2000],
            "red_flags": [str(x)[:300] for x in assessment.get("red_flags", []) if x][:10],
            "requirements_json": json.dumps(result["requirements"], ensure_ascii=False),
            "evaluated_at": now,
        }
    )
    ranking = rank(candidates_table, job["job_id"])
    position = next((i for i, c in enumerate(ranking, 1) if c["candidate_email"] == email), None)

    return respond(
        201,
        {
            "job_id": job["job_id"],
            "job_title": job["title"],
            "candidate_name": name,
            "candidate_email": email,
            **{k: result[k] for k in ("score", "threshold", "mandatory_met", "decision", "decision_reason")},
            "summary": assessment.get("summary", ""),
            "red_flags": assessment.get("red_flags", []),
            # Flat text versions, easy to map into Zapier email steps.
            "strengths_text": "\n".join(f"- {s}" for s in result["strengths"]) or "- none",
            "gaps_text": "\n".join(f"- {g}" for g in result["gaps"]) or "- none",
            "rank": position,
            **dict(zip(("email_subject", "email_body"), build_email(result["decision"], name, job["title"], result["strengths"]))),
            "candidates_for_job": len(ranking),
            "requirements": result["requirements"],
            "evaluated_at": now,
        },
    )


def rank(candidates_table, job_id: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key

    items = candidates_table.query(KeyConditionExpression=Key("job_id").eq(job_id)).get("Items", [])
    return sorted(items, key=lambda c: (c["decision"] != "advance", -int(c["score"]), c["candidate_name"]))


def rankings(event, job):
    jobs_table, candidates_table = tables()
    record = get_job(jobs_table, job)
    if not record:
        return respond(404, {"error": f"unknown job: {unquote(job)}"})
    ranked = rank(candidates_table, record["job_id"])
    return respond(
        200,
        {
            "job_id": record["job_id"],
            "title": record["title"],
            "candidates": [
                {
                    "rank": i,
                    "candidate_name": c["candidate_name"],
                    "candidate_email": c["candidate_email"],
                    "score": c["score"],
                    "decision": c["decision"],
                    "decision_reason": c["decision_reason"],
                    "evaluated_at": c["evaluated_at"],
                }
                for i, c in enumerate(ranked, 1)
            ],
        },
    )


ROUTES = [
    ("GET", re.compile(r"^/jobs/?$"), list_jobs),
    ("GET", re.compile(r"^/jobs/(?P<job>[^/]+)/?$"), read_job),
    ("POST", re.compile(r"^/resumes/parse/?$"), parse_resume),
    ("POST", re.compile(r"^/evaluations/?$"), create_evaluation),
    ("GET", re.compile(r"^/rankings/(?P<job>[^/]+)/?$"), rankings),
]


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path") or "/"
    for route_method, pattern, fn in ROUTES:
        match = pattern.match(path)
        if match and method == route_method:
            try:
                return fn(event, **match.groupdict())
            except ValueError as exc:
                return respond(400, {"error": str(exc)})
            except urllib.error.URLError as exc:
                return respond(502, {"error": f"could not download the file: {exc}"})
    return respond(404, {"error": f"no route for {method} {path}"})
