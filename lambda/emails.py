"""Advance and rejection emails, filled from an evaluation.

POST /evaluations returns `email_subject` and `email_body` for the decision,
so the Zapier Gmail steps only map these two fields.
"""

from __future__ import annotations

TEMPLATES = {
    "advance": {
        "subject": "Next steps for your {job_title} application",
        "body": (
            "Hi {first_name},\n\n"
            "Thank you for applying for the {job_title} role at SmartHire. We reviewed your resume and "
            "would like to move you forward to the next stage of our process.\n\n"
            "What stood out:\n{strengths}\n\n"
            "A member of our team will contact you within three business days to schedule a "
            "30-minute introductory call.\n\n"
            "Best regards,\nSmartHire Recruiting Team"
        ),
    },
    "reject": {
        "subject": "Your {job_title} application",
        "body": (
            "Hi {first_name},\n\n"
            "Thank you for your interest in the {job_title} role at SmartHire and for the time you put "
            "into your application.\n\n"
            "After reviewing your resume against the requirements for this position, we have decided "
            "not to move forward at this time. We did not find a close enough match with the core "
            "requirements of this opening.\n\n"
            "We encourage you to apply again for future roles that match your background.\n\n"
            "Best regards,\nSmartHire Recruiting Team"
        ),
    },
}


def build_email(decision: str, candidate_name: str, job_title: str, strengths: list[str]) -> tuple[str, str]:
    template = TEMPLATES[decision]
    values = {
        "first_name": (candidate_name or "there").split()[0],
        "job_title": job_title,
        "strengths": "\n".join(f"- {s}" for s in strengths[:5]) or "- Your overall background",
    }
    return template["subject"].format(**values), template["body"].format(**values)
