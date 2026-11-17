"""Turn the LLM judge's per-requirement assessment into a score and a decision.

The judge decides, for each requirement, whether the resume shows it (met,
partial or not_met) and quotes its evidence. The numbers and the
advance/reject decision are computed here, in code, from the weights stored
with the job in DynamoDB. The same assessment always gives the same decision,
and a mandatory requirement can never be outweighed by the others.
"""

from __future__ import annotations

import json
import re

STATUS_CREDIT = {"met": 1.0, "partial": 0.5, "not_met": 0.0}


class InvalidAssessment(ValueError):
    pass


def parse_assessment(raw) -> dict:
    """Accept a dict or a JSON string (optionally wrapped in a ```json fence)."""
    if isinstance(raw, dict):
        data = raw
    else:
        text = str(raw or "").strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if fenced:
            text = fenced.group(1)
        elif not text.startswith("{"):
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end > start:
                text = text[start : end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InvalidAssessment(f"assessment is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("assessments"), list):
        raise InvalidAssessment("assessment must be an object with an 'assessments' list")
    return data


def score_candidate(job: dict, assessment: dict) -> dict:
    by_id = {}
    for item in assessment["assessments"]:
        if isinstance(item, dict) and item.get("id"):
            by_id[str(item["id"]).strip()] = item

    rows, earned, total = [], 0.0, 0.0
    missing_mandatory = []
    for req in job["requirements"]:
        item = by_id.get(req["id"], {})
        status = str(item.get("status", "not_met")).strip().lower().replace(" ", "_").replace("-", "_")
        if status not in STATUS_CREDIT:
            status = "not_met"
        weight = float(req["weight"])
        points = weight * STATUS_CREDIT[status]
        earned += points
        total += weight
        if req.get("mandatory") and status != "met":
            missing_mandatory.append(req["id"])
        rows.append(
            {
                "id": req["id"],
                "requirement": req["text"],
                "mandatory": bool(req.get("mandatory")),
                "weight": weight,
                "status": status,
                "points": round(points, 1),
                "evidence": str(item.get("evidence", "")).strip() or "not mentioned",
            }
        )

    score = round(100 * earned / total) if total else 0
    threshold = int(job.get("advance_threshold", 70))
    mandatory_met = not missing_mandatory
    if not mandatory_met:
        decision = "reject"
        reason = "Mandatory requirement not met: " + ", ".join(missing_mandatory)
    elif score < threshold:
        decision = "reject"
        reason = f"Score {score} is below the advance threshold of {threshold}"
    else:
        decision = "advance"
        reason = f"All mandatory requirements met and score {score} >= {threshold}"

    return {
        "score": score,
        "threshold": threshold,
        "mandatory_met": mandatory_met,
        "missing_mandatory": missing_mandatory,
        "decision": decision,
        "decision_reason": reason,
        "requirements": rows,
        "strengths": [r["requirement"] for r in rows if r["status"] == "met"],
        "gaps": [r["requirement"] for r in rows if r["status"] != "met"],
    }
