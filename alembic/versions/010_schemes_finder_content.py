"""schemes_finder v0.1: 7 additional schemes + English translations

Revision ID: 010
Revises: 009
Create Date: 2026-08-24

Extends the 3 scaffolding schemes seeded in migration 005
(``e_shram``, ``pm_suraksha_bima_yojana``, ``karnataka_platform_welfare``)
with 7 more from the PRD §6.4 v1 list, so Schemes Finder ships with a
useful 10-scheme corpus.

New schemes:
  pm_jeevan_jyoti_bima_yojana   Life insurance, all-India
  ayushman_bharat_pmjay         Health cover, all-India (means-tested)
  pm_shram_yogi_maandhan        Pension, all-India, unorganised workers
  rajasthan_platform_welfare    State welfare board, Rajasthan
  atal_pension_yojana           Pension, all-India
  sukanya_samriddhi_yojana      Savings, workers with a daughter under 10
  state_pds_ration_card         Public Distribution System, all states

Multilingual variants (Hindi, Bengali, Tamil) are NOT part of this
migration. They come from ``scripts/translate_schemes.py`` running the
same Sarvam Mayura pipeline that produced the Rights Guide
translations.

Idempotent: uses DELETE-then-INSERT on ``schemes.key`` + tenant_id IS
NULL so re-running picks up any edits without leaving duplicates.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as _sql


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# 7 new schemes — English canonical
# ---------------------------------------------------------------------------
#
# Each entry:
#   key                stable slug used by the API + client
#   state_scope        'all' | state code — matches the schemes column
#   eligibility_rules  JSONB shape used by the matcher (min_age, max_age,
#                      occupations, states, gender, requires_children,
#                      requires_daughter, requires_eshram)
#   apply_url          official government portal (canonical source)
#   docs_needed        list of {name, note?}
#   estimated_time     free-form string
#   icon               Lucide icon name from frontend/src/lib/icons.ts
#   sort_order         list ordering; groups by kind (insurance, pension, …)
#   translation.en     { name, description, apply_note }
#
# Content follows the same lawyer-safe rules as Rights Guide:
#   - Describe the scheme, do not claim eligibility for any individual.
#   - Link to the official portal as the canonical source for benefit
#     amounts (which change).
#   - Include the amounts where they are structurally stable and
#     well-documented (PMSBY, APY tiers) — those are the whole point of
#     the scheme and portal-linking still applies for current figures.

SCHEMES = [
    dict(
        key="pm_jeevan_jyoti_bima_yojana",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "min_age": 18,
            "max_age": 50,
            "requires_bank_account": True,
        },
        apply_url="https://jansuraksha.gov.in",
        docs_needed=[
            {"name": "Aadhaar"},
            {"name": "Bank account", "note": "premium is auto-debited"},
        ],
        estimated_time="One visit to your bank",
        icon="ShieldPlus",
        sort_order=20,
        translation_en=dict(
            name="PM Jeevan Jyoti Bima Yojana",
            description=(
                "Government-backed term life insurance for anyone with a bank "
                "account, aged 18 to 50. Cover of Rs 2 lakh in case of death "
                "for any reason during the policy year. Renewable annually. "
                "Premium is a fixed low rupee amount auto-debited from the "
                "linked bank account. See the official portal for the current "
                "premium and enrolment window."
            ),
            apply_note="Enrol through your bank, either in-branch or via your bank's app.",
        ),
    ),
    dict(
        key="ayushman_bharat_pmjay",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "min_age": 0,
            "means_tested": True,
        },
        apply_url="https://pmjay.gov.in",
        docs_needed=[
            {"name": "Aadhaar"},
            {"name": "Family ID / ration card"},
        ],
        estimated_time="Eligibility check first; enrolment 15-30 minutes",
        icon="HeartPulse",
        sort_order=30,
        translation_en=dict(
            name="Ayushman Bharat PM-JAY",
            description=(
                "Health insurance cover for eligible low-income families, "
                "administered by the National Health Authority. Covers "
                "secondary and tertiary care hospitalisation at empanelled "
                "hospitals across India. Eligibility is means-tested and "
                "based on the SECC 2011 database. Check whether your family "
                "is on the eligibility list before beginning enrolment."
            ),
            apply_note=(
                "Check eligibility on the PM-JAY portal or at your nearest "
                "Common Service Centre before enrolling."
            ),
        ),
    ),
    dict(
        key="pm_shram_yogi_maandhan",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "min_age": 18,
            "max_age": 40,
            "requires_eshram": True,
        },
        apply_url="https://maandhan.in",
        docs_needed=[
            {"name": "Aadhaar"},
            {"name": "e-Shram UAN"},
            {"name": "Bank account", "note": "for monthly contribution debit"},
        ],
        estimated_time="15-20 minutes at a Common Service Centre",
        icon="Landmark",
        sort_order=40,
        translation_en=dict(
            name="PM Shram Yogi Maandhan (Pension)",
            description=(
                "Voluntary pension scheme for unorganised workers earning "
                "under a set monthly income ceiling. Provides a monthly "
                "pension after age 60. Contribution is age-based and matched "
                "one-for-one by the central government. Sign-up is easiest "
                "through a Common Service Centre; e-Shram registration is a "
                "prerequisite. See the portal for current contribution "
                "amounts and the income ceiling."
            ),
            apply_note=(
                "Visit your nearest Common Service Centre with Aadhaar and "
                "your e-Shram UAN."
            ),
        ),
    ),
    dict(
        key="rajasthan_platform_welfare",
        state_scope="rajasthan",
        eligibility_rules={
            "occupations": ["delivery", "cab", "any"],
            "states": ["rajasthan"],
        },
        apply_url="https://labour.rajasthan.gov.in",
        docs_needed=[
            {"name": "Aadhaar"},
            {"name": "Proof of platform work", "note": "app screenshot, ID, or contract"},
        ],
        estimated_time="20-30 minutes at the labour department portal",
        icon="Shield",
        sort_order=50,
        translation_en=dict(
            name="Rajasthan Platform-Based Gig Workers Welfare Board",
            description=(
                "State welfare board established under the Rajasthan "
                "Platform Based Gig Workers (Registration and Welfare) Act, "
                "2023. Registered gig workers become eligible for state "
                "welfare schemes funded by a cess on aggregator "
                "transactions. Scope and benefits are notified by the state "
                "labour department; check the department's portal for the "
                "current scheme list."
            ),
            apply_note=(
                "Register through the Rajasthan labour department portal. "
                "For help, contact the state labour commissioner's office."
            ),
        ),
    ),
    dict(
        key="atal_pension_yojana",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "min_age": 18,
            "max_age": 40,
            "requires_bank_account": True,
        },
        apply_url="https://npscra.nsdl.co.in/scheme-details.php",
        docs_needed=[
            {"name": "Aadhaar"},
            {"name": "Bank account", "note": "for auto-debit of contribution"},
        ],
        estimated_time="One visit to your bank",
        icon="Landmark",
        sort_order=60,
        translation_en=dict(
            name="Atal Pension Yojana",
            description=(
                "Central government pension scheme for citizens aged 18 to "
                "40, delivered through banks. Contribution is auto-debited "
                "and the subscriber receives a guaranteed monthly pension "
                "from age 60 onwards. Pension tier depends on contribution "
                "level; see the official documentation for current "
                "amounts."
            ),
            apply_note="Enrol through your bank branch or via your bank's app.",
        ),
    ),
    dict(
        key="sukanya_samriddhi_yojana",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "requires_daughter": True,
            "max_daughter_age": 10,
        },
        apply_url="https://www.indiapost.gov.in/Financial/Pages/Content/Sukanya-Samriddhi-Account.aspx",
        docs_needed=[
            {"name": "Daughter's birth certificate"},
            {"name": "Guardian's ID and address proof"},
            {"name": "Photographs"},
        ],
        estimated_time="30-45 minutes at a post office or authorised bank",
        icon="Award",
        sort_order=70,
        translation_en=dict(
            name="Sukanya Samriddhi Yojana",
            description=(
                "Government savings scheme for guardians of girl children "
                "under 10. Opens at a post office or authorised bank. "
                "Deposits earn tax-free interest at a rate notified quarterly "
                "by the Ministry of Finance. Maturity is 21 years from "
                "account opening or on the daughter's marriage after 18. "
                "See the India Post page for the current interest rate and "
                "deposit limits."
            ),
            apply_note=(
                "Open at your nearest post office or an authorised bank "
                "branch with the daughter's birth certificate."
            ),
        ),
    ),
    dict(
        key="state_pds_ration_card",
        state_scope="all",
        eligibility_rules={
            "occupations": ["any"],
            "means_tested": True,
        },
        apply_url="https://nfsa.gov.in",
        docs_needed=[
            {"name": "Aadhaar", "note": "of all household members"},
            {"name": "Proof of address"},
            {"name": "Income declaration", "note": "requirements vary by state"},
        ],
        estimated_time="Application at the state food and civil supplies portal; timelines vary",
        icon="HandCoins",
        sort_order=80,
        translation_en=dict(
            name="State Ration Card (Public Distribution System)",
            description=(
                "State-issued ration cards under the National Food Security "
                "Act, 2013 give eligible households access to subsidised "
                "food grains through the Public Distribution System. Each "
                "state operates its own portal for issuance. Eligibility is "
                "means-tested and defined by the state, drawing on the "
                "SECC 2011 database."
            ),
            apply_note=(
                "Search \"[your state] ration card apply\" for the state "
                "food and civil supplies portal. The Aadhaar of every "
                "household member is required."
            ),
        ),
    ),
]


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_DELETE_SCHEME = """
    DELETE FROM schemes
     WHERE key = :key
       AND tenant_id IS NULL;
"""

_INSERT_SCHEME = """
    INSERT INTO schemes
        (key, state_scope, eligibility_rules, apply_url, docs_needed,
         estimated_time, icon, sort_order, is_active)
    VALUES
        (:key, :state_scope, CAST(:eligibility_rules AS jsonb), :apply_url,
         CAST(:docs_needed AS jsonb), :estimated_time, :icon, :sort_order,
         true)
    RETURNING id;
"""

_INSERT_TRANSLATION = """
    INSERT INTO scheme_translations (scheme_id, language, name, description, apply_note)
    VALUES (:scheme_id, :language, :name, :description, :apply_note);
"""


def upgrade() -> None:
    bind = op.get_bind()

    for scheme in SCHEMES:
        # Cascade delete removes any prior translations too.
        bind.execute(_sql(_DELETE_SCHEME), {"key": scheme["key"]})

        row = bind.execute(_sql(_INSERT_SCHEME), {
            "key": scheme["key"],
            "state_scope": scheme["state_scope"],
            "eligibility_rules": json.dumps(scheme["eligibility_rules"]),
            "apply_url": scheme["apply_url"],
            "docs_needed": json.dumps(scheme["docs_needed"]),
            "estimated_time": scheme["estimated_time"],
            "icon": scheme["icon"],
            "sort_order": scheme["sort_order"],
        }).first()
        scheme_id = row[0]

        t = scheme["translation_en"]
        bind.execute(_sql(_INSERT_TRANSLATION), {
            "scheme_id": scheme_id,
            "language": "en",
            "name": t["name"],
            "description": t["description"],
            "apply_note": t["apply_note"],
        })


def downgrade() -> None:
    bind = op.get_bind()
    for scheme in SCHEMES:
        bind.execute(_sql("DELETE FROM schemes WHERE key = :key AND tenant_id IS NULL"),
                     {"key": scheme["key"]})
