"""complaint_helper v0.1: refresh 3 templates + seed 2 new (5 total)

Revision ID: 011
Revises: 010
Create Date: 2026-08-24

Extends the 3 scaffolding templates seeded in migration 005
(``wage_theft``, ``injury``, ``harassment``) with 2 more from the
PRD §6.5 v1 list so Complaint Helper ships with a full 5-topic set:

  wage_theft   Unpaid or under-paid gig work
  injury       Injury while performing gig work
  dismissal    Unexplained deactivation from a platform
  harassment   Harassment by platform staff or customer
  insurance    Insurance claim denial or non-payout

Every template:
- Uses Handlebars-style ``{{fields.x}}`` and ``{{routing.primary.authority}}``
  placeholders. The renderer (``app/conversation_studio/render.py``)
  drops the enclosing sentence when a placeholder fails to resolve, so
  a partially-filled form never leaks ``{{x}}`` scaffolding to the
  worker.
- Follows the same legal-safety rules as Rights Guide: factual, no
  strategic advice, statute-anchored where relevant, escalation to
  India Labourline everywhere.

Multilingual variants follow via ``scripts/translate_complaints.py``.

Idempotent: DELETE-then-INSERT per (topic_key, 'en', tenant_id IS NULL).
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as _sql


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Templates (English canonical)
# ---------------------------------------------------------------------------

# Common personal-info fields shared across all templates.
_PERSONAL_FIELDS = [
    {"key": "name",    "label": "Your full name", "type": "text"},
    {"key": "phone",   "label": "Your phone number", "type": "text"},
    {"key": "address", "label": "Your address", "type": "text"},
    {"key": "city",    "label": "City where you work", "type": "text"},
    {"key": "occupation", "label": "Type of work", "type": "select",
     "options": ["delivery rider", "cab driver", "auto driver",
                 "domestic worker", "other"]},
    {"key": "platform",  "label": "Platform name", "type": "text",
     "help": "e.g. Swiggy, Uber, Urban Company"},
    {"key": "worker_id", "label": "Your worker / partner ID on the platform", "type": "text"},
]


TEMPLATES = [
    dict(
        topic_key="wage_theft",
        title="Complaint about unpaid or under-paid gig work",
        body=(
            "To: {{routing.primary.authority}}\n\n"
            "Subject: Complaint regarding unpaid wages for gig work\n\n"
            "I am {{fields.name}}, a {{fields.occupation}} working on the "
            "{{fields.platform}} platform in {{fields.city}}. My worker "
            "ID on the platform is {{fields.worker_id}}.\n\n"
            "On {{fields.incident_date}}, I performed work for which I "
            "was to be paid Rs {{fields.expected_amount}}. The amount "
            "actually received was Rs {{fields.actual_amount}}. The "
            "reason given by the platform, if any, was: "
            "{{fields.platform_reason}}.\n\n"
            "I raised this through the platform's in-app support on "
            "{{fields.support_contact_date}} but the matter is not "
            "resolved.\n\n"
            "I request your office to take up this matter under the "
            "applicable labour welfare provisions.\n\n"
            "Sincerely,\n"
            "{{fields.name}}\n"
            "{{fields.phone}}\n"
            "{{fields.address}}"
        ),
        routing=[
            {"authority": "State Labour Commissioner",
             "note": "Primary channel for wage disputes; can summon the platform."},
            {"authority": "India Labourline",
             "contact": "1800-419-1550",
             "note": "National helpline; will route to your state's office."},
            {"authority": "Consumer Court",
             "note": "Alternate channel for disputes over the transaction itself."},
        ],
        required_fields=_PERSONAL_FIELDS + [
            {"key": "incident_date",  "label": "When was the work performed?", "type": "text",
             "help": "e.g. 12 August 2026"},
            {"key": "expected_amount", "label": "Amount you were to be paid (₹)", "type": "text"},
            {"key": "actual_amount",   "label": "Amount actually received (₹)", "type": "text"},
            {"key": "platform_reason", "label": "Reason the platform gave, if any", "type": "text",
             "help": "Leave blank if no reason was given."},
            {"key": "support_contact_date", "label": "Date you contacted platform support", "type": "text"},
        ],
    ),
    dict(
        topic_key="injury",
        title="Complaint about an injury while performing gig work",
        body=(
            "To: {{routing.primary.authority}}\n\n"
            "Subject: Injury while performing platform-based gig work\n\n"
            "I am {{fields.name}}, a {{fields.occupation}} working on the "
            "{{fields.platform}} platform in {{fields.city}}. My worker "
            "ID on the platform is {{fields.worker_id}}.\n\n"
            "On {{fields.incident_date}}, I was injured while performing "
            "work assigned through the {{fields.platform}} app. Nature "
            "of injury: {{fields.injury_description}}. Location where "
            "the incident occurred: {{fields.incident_location}}.\n\n"
            "Medical care received: {{fields.medical_care}}. Estimated "
            "medical expense to date: Rs {{fields.medical_expense}}. "
            "Days unable to work since the incident: "
            "{{fields.days_off_work}}.\n\n"
            "I raised this with the platform's in-app support on "
            "{{fields.support_contact_date}}. The platform's insurance "
            "policy details are: {{fields.insurance_details}}.\n\n"
            "I request your office to guide me on the applicable "
            "welfare provisions and the platform's obligations under "
            "the Central Motor Vehicles Rules (2024 amendment) and the "
            "Code on Social Security, 2020.\n\n"
            "Sincerely,\n"
            "{{fields.name}}\n"
            "{{fields.phone}}\n"
            "{{fields.address}}"
        ),
        routing=[
            {"authority": "Platform in-app support",
             "note": "Start here to create a documented ticket."},
            {"authority": "State Labour Commissioner",
             "note": "Escalate here if the platform does not respond."},
            {"authority": "India Labourline",
             "contact": "1800-419-1550",
             "note": "For guidance on ESIC or state welfare-board accident schemes."},
            {"authority": "State Welfare Board (if registered)",
             "note": "Karnataka, Rajasthan currently. Others as notified."},
        ],
        required_fields=_PERSONAL_FIELDS + [
            {"key": "incident_date",     "label": "Date of injury", "type": "text"},
            {"key": "injury_description", "label": "What happened?", "type": "text",
             "help": "Brief description of the injury."},
            {"key": "incident_location", "label": "Where did the incident happen?", "type": "text"},
            {"key": "medical_care",      "label": "Medical care received", "type": "text",
             "help": "e.g. hospital name, treatment received."},
            {"key": "medical_expense",   "label": "Medical expense so far (₹)", "type": "text"},
            {"key": "days_off_work",     "label": "Days unable to work", "type": "text"},
            {"key": "support_contact_date", "label": "Date you contacted platform support", "type": "text"},
            {"key": "insurance_details", "label": "Platform's insurance policy details, if known", "type": "text",
             "help": "Leave blank if you don't have the details yet."},
        ],
    ),
    dict(
        topic_key="dismissal",
        title="Complaint about deactivation from a platform",
        body=(
            "To: {{routing.primary.authority}}\n\n"
            "Subject: Complaint regarding sudden deactivation from platform\n\n"
            "I am {{fields.name}}, a {{fields.occupation}} who was "
            "working on the {{fields.platform}} platform in "
            "{{fields.city}} for {{fields.tenure}}. My worker ID on the "
            "platform is {{fields.worker_id}}.\n\n"
            "On {{fields.deactivation_date}}, my account was deactivated "
            "without prior notice. The reason communicated by the "
            "platform, if any, was: {{fields.deactivation_reason}}.\n\n"
            "This is my primary source of livelihood. My last completed "
            "work on the platform was on {{fields.last_work_date}}.\n\n"
            "I raised an appeal through the platform's in-app support on "
            "{{fields.support_contact_date}}. Response received: "
            "{{fields.support_response}}.\n\n"
            "I request your office to take up this matter under the "
            "applicable labour welfare provisions and Fairwork India's "
            "principle on fair management, which requires meaningful "
            "notice and an appeal process for platform-based workers.\n\n"
            "Sincerely,\n"
            "{{fields.name}}\n"
            "{{fields.phone}}\n"
            "{{fields.address}}"
        ),
        routing=[
            {"authority": "State Labour Commissioner",
             "note": "Primary channel for wrongful dismissal grievances."},
            {"authority": "India Labourline",
             "contact": "1800-419-1550",
             "note": "National helpline; guides on next steps."},
            {"authority": "Platform grievance officer",
             "note": "By law, aggregators must have a grievance redressal officer."},
        ],
        required_fields=_PERSONAL_FIELDS + [
            {"key": "tenure",              "label": "How long did you work on the platform?", "type": "text",
             "help": "e.g. 2 years"},
            {"key": "deactivation_date",   "label": "Date your account was deactivated", "type": "text"},
            {"key": "deactivation_reason", "label": "Reason the platform gave, if any", "type": "text",
             "help": "Leave blank if no reason was given."},
            {"key": "last_work_date",      "label": "Date of your last completed work", "type": "text"},
            {"key": "support_contact_date", "label": "Date you appealed via in-app support", "type": "text"},
            {"key": "support_response",     "label": "Platform's response to your appeal", "type": "text",
             "help": "Leave blank if no response yet."},
        ],
    ),
    dict(
        topic_key="harassment",
        title="Complaint about harassment while performing gig work",
        body=(
            "To: {{routing.primary.authority}}\n\n"
            "Subject: Complaint regarding harassment during platform-based gig work\n\n"
            "I am {{fields.name}}, a {{fields.occupation}} working on the "
            "{{fields.platform}} platform in {{fields.city}}. My worker "
            "ID on the platform is {{fields.worker_id}}.\n\n"
            "On {{fields.incident_date}}, at {{fields.incident_location}}, "
            "I experienced the following incident: "
            "{{fields.incident_description}}. Person(s) involved: "
            "{{fields.person_involved}}.\n\n"
            "I raised this through the platform's in-app support on "
            "{{fields.support_contact_date}}. Response received: "
            "{{fields.support_response}}.\n\n"
            "I request your office to take up this matter under the "
            "applicable provisions of the Sexual Harassment of Women at "
            "Workplace (Prevention, Prohibition and Redressal) Act, "
            "2013, and to advise on the correct forum given the "
            "platform-based nature of the work.\n\n"
            "Sincerely,\n"
            "{{fields.name}}\n"
            "{{fields.phone}}\n"
            "{{fields.address}}"
        ),
        routing=[
            {"authority": "Platform Internal Committee (IC)",
             "note": "The aggregator's own IC under the POSH Act, 2013."},
            {"authority": "Local police",
             "contact": "112",
             "note": "For safety-critical or criminal matters, do not wait — call 112."},
            {"authority": "India Labourline",
             "contact": "1800-419-1550",
             "note": "For guidance on the correct forum."},
        ],
        required_fields=_PERSONAL_FIELDS + [
            {"key": "incident_date",       "label": "Date of the incident", "type": "text"},
            {"key": "incident_location",   "label": "Where did it happen?", "type": "text"},
            {"key": "incident_description", "label": "What happened?", "type": "text",
             "help": "Describe the incident in your own words."},
            {"key": "person_involved",     "label": "Who was involved?", "type": "text",
             "help": "Name or description of the person(s)."},
            {"key": "support_contact_date", "label": "Date you contacted platform support", "type": "text"},
            {"key": "support_response",     "label": "Platform's response", "type": "text",
             "help": "Leave blank if no response yet."},
        ],
    ),
    dict(
        topic_key="insurance",
        title="Complaint about insurance claim denial",
        body=(
            "To: {{routing.primary.authority}}\n\n"
            "Subject: Complaint regarding denial of insurance claim\n\n"
            "I am {{fields.name}}, a {{fields.occupation}} working on the "
            "{{fields.platform}} platform in {{fields.city}}. My worker "
            "ID on the platform is {{fields.worker_id}}. My insurance "
            "policy is {{fields.policy_number}} with "
            "{{fields.insurer_name}}.\n\n"
            "I filed a claim on {{fields.claim_date}} for "
            "{{fields.claim_reason}}. The claim amount sought was Rs "
            "{{fields.claim_amount}}.\n\n"
            "The claim was denied on {{fields.denial_date}}. The reason "
            "given by the insurer was: {{fields.denial_reason}}. I "
            "believe this is inconsistent with the policy terms because: "
            "{{fields.disagreement}}.\n\n"
            "Supporting documents I have: {{fields.documents_held}}.\n\n"
            "I request your office to review this matter under the "
            "applicable IRDAI regulations and advise on next steps.\n\n"
            "Sincerely,\n"
            "{{fields.name}}\n"
            "{{fields.phone}}\n"
            "{{fields.address}}"
        ),
        routing=[
            {"authority": "Insurer's Grievance Redressal Officer",
             "note": "Every IRDAI-registered insurer must have one; look on the insurer's website."},
            {"authority": "IRDAI Bima Bharosa (IRDA Grievance)",
             "url": "https://bimabharosa.irdai.gov.in",
             "note": "Central portal for insurance complaints across insurers."},
            {"authority": "Insurance Ombudsman",
             "note": "For unresolved complaints, based on your region."},
            {"authority": "India Labourline",
             "contact": "1800-419-1550",
             "note": "General guidance if the policy was provided through the platform."},
        ],
        required_fields=_PERSONAL_FIELDS + [
            {"key": "insurer_name",   "label": "Name of the insurer", "type": "text"},
            {"key": "policy_number",  "label": "Policy number", "type": "text"},
            {"key": "claim_date",     "label": "Date the claim was filed", "type": "text"},
            {"key": "claim_reason",   "label": "What the claim was for", "type": "text",
             "help": "e.g. accident hospitalisation, vehicle damage"},
            {"key": "claim_amount",   "label": "Amount claimed (₹)", "type": "text"},
            {"key": "denial_date",    "label": "Date claim was denied", "type": "text"},
            {"key": "denial_reason",  "label": "Reason the insurer gave", "type": "text"},
            {"key": "disagreement",   "label": "Why you disagree with the denial", "type": "text",
             "help": "Reference the policy clause you think supports your claim, if you can."},
            {"key": "documents_held", "label": "Documents you have to support your claim", "type": "text",
             "help": "e.g. policy PDF, bills, medical reports"},
        ],
    ),
]


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_DELETE = """
    DELETE FROM complaint_templates
     WHERE topic_key = :topic_key AND language = 'en' AND tenant_id IS NULL;
"""
_INSERT = """
    INSERT INTO complaint_templates
        (topic_key, language, title, body, routing, required_fields, is_active)
    VALUES
        (:topic_key, 'en', :title, :body, CAST(:routing AS jsonb),
         CAST(:required_fields AS jsonb), true);
"""


def upgrade() -> None:
    bind = op.get_bind()
    for tpl in TEMPLATES:
        bind.execute(_sql(_DELETE), {"topic_key": tpl["topic_key"]})
        bind.execute(_sql(_INSERT), {
            "topic_key": tpl["topic_key"],
            "title": tpl["title"],
            "body": tpl["body"],
            "routing": json.dumps(tpl["routing"]),
            "required_fields": json.dumps(tpl["required_fields"]),
        })


def downgrade() -> None:
    # Leave the topic rows in place — reverting to migration 005's older
    # copy is a re-upgrade path (downgrade to 005, upgrade to 011).
    pass
