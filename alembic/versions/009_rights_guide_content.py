"""rights_guide v0.1 content: five English fact cards (canonical)

Revision ID: 009
Revises: 008
Create Date: 2026-08-23

Ships the first production content for the Rights Guide module. Five
English fact cards, statute-cited, procedural action steps only. Bound
by the rules in ``docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md``.

Multilingual variants (Hindi, Bengali, Tamil) are NOT part of this
migration. They will be produced by a separate Mayura translation pass
against the English canonical rows here, land at ``is_active = false``,
and only flip to ``true`` after a native-speaker review completes the
per-card checklist. See ``docs/RIGHTS_GUIDE_CONTENT_GUIDELINES.md`` for
the translation protocol.

This migration:
- REWRITES the three English scaffolding rows seeded in migration 005
  (``minimum_wage``, ``injury_on_the_job``, ``grievance_escalation``)
  so their copy adheres to the current legal-safety rules.
- INSERTS two new English cards (``e_shram_registration``,
  ``contract_fairness``).

All INSERT/UPDATE writes are idempotent under
``ON CONFLICT (topic_key, language, tenant_id) DO UPDATE`` so this
migration can be re-run without doubling rows during development. The
uniqueness constraint was set up in migration 005.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Canonical English content — five cards
# ---------------------------------------------------------------------------
#
# All five rows follow the same shape. Summary is 2-3 short paragraphs
# (statement of law, not advice). Citation carries statute name + section
# where applicable + a stable government URL. Action steps are procedural
# only (register, call, contact) and every card routes to India
# Labourline (1800-419-1550) as the standing escalation.

# The action_steps JSONB shape is [{label, description, url?}].

CARDS = [
    dict(
        topic_key="minimum_wage",
        title="Minimum wage protection for gig workers",
        summary=(
            "Central and state minimum wage laws have historically applied to formal employees. "
            "Platforms have argued that gig workers are \"partners\" rather than employees, "
            "keeping the Minimum Wages Act 1948 at arm's length.\n\n"
            "The Code on Social Security 2020 changed the framing. Sections 113 and 114 create "
            "the category \"platform-based gig worker\" and mandate a national social security "
            "fund. This does not automatically bring gig workers under the Minimum Wages Act, "
            "but it establishes a legal basis for state-level welfare schemes with floor-price "
            "protections.\n\n"
            "Karnataka and Rajasthan have operational welfare boards today. These boards are "
            "the practical route to state-mandated benefits. Other states are drafting similar "
            "legislation."
        ),
        citation=(
            "Code on Social Security, 2020 (Act No. 36 of 2020), Sections 113-114. "
            "Ministry of Labour and Employment, Government of India. "
            "https://labour.gov.in/sites/default/files/ss_code_gazette.pdf"
        ),
        action_steps=[
            {
                "label": "Register on e-Shram",
                "description": (
                    "The portal issues a Universal Account Number that unlocks central welfare "
                    "schemes. Registration is free."
                ),
                "url": "https://eshram.gov.in",
            },
            {
                "label": "Check your state welfare board",
                "description": (
                    "Karnataka and Rajasthan have gig-worker-specific boards. Search "
                    "\"[your state] gig workers welfare board\" for the office in your state."
                ),
            },
            {
                "label": "Call India Labourline",
                "description": (
                    "For any complaint about wage theft or pay that is lower than what your "
                    "agreement documents. Phone: 1800-419-1550."
                ),
                "url": "tel:1800-419-1550",
            },
        ],
        icon="IndianRupee",
        sort_order=10,
    ),
    dict(
        topic_key="injury_on_the_job",
        title="Injury while working on a platform",
        summary=(
            "Traffic and workplace injuries are a documented risk for delivery riders, cab "
            "drivers, and gig workers in trades. Research from the Ola Mobility Institute on "
            "working conditions of delivery workers records heat exhaustion and road-safety "
            "incidents as common occurrences.\n\n"
            "Aggregator platforms may offer accident insurance, typically underwritten by "
            "IRDAI-registered insurers. Coverage terms are set by the platform's policy "
            "document, which the worker is entitled to see. The Ministry of Road Transport "
            "and Highways amended the Central Motor Vehicles Rules in 2024 to place explicit "
            "responsibility on aggregators for driver welfare, including safety training and "
            "insurance obligations.\n\n"
            "The Employees' State Insurance Corporation (ESIC) provides medical and cash "
            "benefits to covered employees. Whether a gig worker qualifies under ESIC depends "
            "on the classification question that is actively being litigated. State welfare "
            "boards (Karnataka, Rajasthan) run separate accident schemes for platform-based "
            "gig workers."
        ),
        citation=(
            "Central Motor Vehicles Rules, 2024 amendment. Ministry of Road Transport and "
            "Highways. Code on Social Security, 2020 (Act No. 36 of 2020), Chapter IX (ESIC "
            "provisions)."
        ),
        action_steps=[
            {
                "label": "Ask the platform for the insurance policy document",
                "description": (
                    "It is your right to see the coverage terms. Keep a copy in a place you "
                    "can find later."
                ),
            },
            {
                "label": "Register on e-Shram",
                "description": (
                    "Some accident-related benefits attach to registered workers."
                ),
                "url": "https://eshram.gov.in",
            },
            {
                "label": "Call India Labourline",
                "description": (
                    "For guidance on filing under state welfare board schemes or ESIC where "
                    "applicable. Phone: 1800-419-1550."
                ),
                "url": "tel:1800-419-1550",
            },
        ],
        icon="HeartPulse",
        sort_order=20,
    ),
    dict(
        topic_key="grievance_escalation",
        title="How to file a grievance about platform work",
        summary=(
            "Every gig worker has multiple parallel routes to escalate a grievance about pay, "
            "safety, dismissal, or platform policy. These are not mutually exclusive channels. "
            "Most disputes benefit from starting with the platform's own customer support so "
            "there is a documented ticket history, then escalating to statutory authorities.\n\n"
            "The Ministry of Labour and Employment operates India Labourline, a national "
            "helpline for labour issues. State Labour Commissioners handle wage disputes and "
            "workplace grievances at the state level. The e-Shram grievance cell handles "
            "issues related to registration and central welfare schemes.\n\n"
            "For workplace harassment, the Sexual Harassment of Women at Workplace (Prevention, "
            "Prohibition and Redressal) Act 2013 requires most workplaces to have an Internal "
            "Committee. The Act's application to gig work is being tested; the aggregator "
            "platform's own Internal Committee is a starting point for complaints against "
            "platform staff."
        ),
        citation=(
            "Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) "
            "Act, 2013. Ministry of Women and Child Development. India Labourline, Ministry "
            "of Labour and Employment."
        ),
        action_steps=[
            {
                "label": "Start with the platform's in-app support",
                "description": (
                    "Document the ticket number, the exact time you filed, and every response. "
                    "Screenshots are the strongest evidence for later escalation."
                ),
            },
            {
                "label": "Call India Labourline",
                "description": (
                    "National helpline; guides workers on the next escalation step based on "
                    "the specific complaint. Phone: 1800-419-1550."
                ),
                "url": "tel:1800-419-1550",
            },
            {
                "label": "File with your State Labour Commissioner",
                "description": (
                    "Search \"[your state] labour commissioner\" for the office contact. "
                    "Every state has one."
                ),
            },
        ],
        icon="MessageSquare",
        sort_order=30,
    ),
    dict(
        topic_key="e_shram_registration",
        title="e-Shram registration for gig workers",
        summary=(
            "e-Shram is the central government's registry of unorganised workers, launched in "
            "2021 by the Ministry of Labour and Employment. Over 30 crore workers were "
            "registered on the portal as of 2024.\n\n"
            "Registration is free. It issues each worker a Universal Account Number (UAN), a "
            "12-digit identifier that ties together central welfare scheme eligibility. State "
            "welfare boards and future gig-worker schemes reference this UAN.\n\n"
            "Gig workers are explicitly recognised on the e-Shram portal following the Code on "
            "Social Security 2020's category recognition. Registration on e-Shram is typically "
            "a prerequisite for state welfare board benefits (Karnataka, Rajasthan) and for "
            "central schemes like PM Suraksha Bima Yojana."
        ),
        citation=(
            "e-Shram portal, Ministry of Labour and Employment, Government of India. "
            "https://eshram.gov.in"
        ),
        action_steps=[
            {
                "label": "Register on e-Shram",
                "description": (
                    "The portal requires an Aadhaar-linked mobile number. Registration takes "
                    "about 10 minutes."
                ),
                "url": "https://eshram.gov.in",
            },
            {
                "label": "Keep your UAN safe",
                "description": (
                    "You will need it for state welfare board applications and for many scheme "
                    "applications later."
                ),
            },
            {
                "label": "Never pay a fee",
                "description": (
                    "Registration is entirely free. Refuse anyone who asks for money to "
                    "\"help\" you register."
                ),
            },
        ],
        icon="IdCard",
        sort_order=40,
    ),
    dict(
        topic_key="contract_fairness",
        title="How to read a platform contract",
        summary=(
            "Platform agreements often run 40 to 90 clauses, drafted by the platform's legal "
            "team. Fairwork India, a research collaboration led by IIIT-Bangalore and the "
            "University of Oxford, has published annual ratings of major Indian gig platforms "
            "since 2020 across five principles: fair pay, fair conditions, fair contracts, "
            "fair management, and fair representation.\n\n"
            "The \"fair contracts\" principle asks whether workers can access the agreement "
            "they signed, whether it is in a language they can read, and whether unilateral "
            "changes give them meaningful notice. These are the same signals a worker can look "
            "for in their own agreement.\n\n"
            "Sreshtha's Contract Reader (available on this account) walks through a contract "
            "clause by clause in the worker's language, flags unfavourable terms with a "
            "colour code, and notes when a clause references or contradicts Indian labour "
            "statutes."
        ),
        citation=(
            "Fairwork India, Annual Ratings of Digital Labour Platforms in India. "
            "IIIT-Bangalore and University of Oxford. "
            "https://fair.work/en/ratings/india/"
        ),
        action_steps=[
            {
                "label": "Use Contract Reader",
                "description": (
                    "Upload your platform agreement (PDF or phone photo) and get a "
                    "clause-by-clause explanation in your language."
                ),
                "url": "/contracts",
            },
            {
                "label": "Ask for a copy in writing",
                "description": (
                    "If your platform has never given you a downloadable copy of your "
                    "agreement, ask their customer support in-app. Save the screenshot of "
                    "your request."
                ),
            },
            {
                "label": "Read Fairwork India's latest India report",
                "description": (
                    "See how the platforms in your city rate."
                ),
                "url": "https://fair.work/en/ratings/india/",
            },
        ],
        icon="FileText",
        sort_order=50,
    ),
]


# ---------------------------------------------------------------------------
# Upgrade / downgrade
# ---------------------------------------------------------------------------

# NOTE on the UPSERT shape:
# - `::jsonb` collides with SQLAlchemy's ':param' binding — use CAST().
# - ON CONFLICT would need `NULLS NOT DISTINCT` on the unique constraint
#   to match rows where tenant_id IS NULL (Postgres treats NULL != NULL
#   in unique indexes). Simpler + more portable: DELETE the shared-
#   tenant row for (topic_key, 'en') first, then INSERT.
_DELETE_EXISTING = """
    DELETE FROM fact_cards
    WHERE topic_key = :topic_key
      AND language = 'en'
      AND tenant_id IS NULL;
"""
_INSERT = """
    INSERT INTO fact_cards
        (topic_key, language, title, summary, citation, action_steps, icon, sort_order, is_active)
    VALUES
        (:topic_key, 'en', :title, :summary, :citation, CAST(:action_steps AS jsonb), :icon, :sort_order, true);
"""


def upgrade() -> None:
    import json
    from sqlalchemy import text as _text

    bind = op.get_bind()
    for card in CARDS:
        params = {
            "topic_key": card["topic_key"],
            "title": card["title"],
            "summary": card["summary"],
            "citation": card["citation"],
            "action_steps": json.dumps(card["action_steps"]),
            "icon": card["icon"],
            "sort_order": card["sort_order"],
        }
        bind.execute(_text(_DELETE_EXISTING), {"topic_key": card["topic_key"]})
        bind.execute(_text(_INSERT), params)


def downgrade() -> None:
    # Do NOT delete rows here — a downgrade should revert copy to the
    # migration-005 scaffolding, not remove the topic keys entirely. Since
    # the earlier copy is preserved in that migration's source, a
    # downgrade + re-upgrade path is `alembic downgrade 005 && alembic
    # upgrade head`. Nothing to do here.
    pass
