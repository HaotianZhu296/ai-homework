# Email templates

Used in the two Gmail steps of the Zap. `{{...}}` are fields mapped from the
`POST /evaluations` webhook step.

## Advance

**Subject:** Next steps for your {{job_title}} application

Hi {{candidate_name}},

Thank you for applying for the {{job_title}} role. We reviewed your resume and would like to move you forward to the next stage of our process.

What stood out:
{{strengths_text}}

A member of our team will contact you within three business days to schedule a 30-minute introductory call.

Best regards,
SmartHire Recruiting Team

## Reject

**Subject:** Your {{job_title}} application

Hi {{candidate_name}},

Thank you for your interest in the {{job_title}} role and for the time you put into your application.

After reviewing your resume against the requirements for this position, we have decided not to move forward at this time. We did not find a close enough match with the core requirements of this opening.

We encourage you to apply again for future roles that match your background.

Best regards,
SmartHire Recruiting Team
