"""seed 15 clause_rules for the highest-frequency gig-worker patterns

Revision ID: 015
Revises: 014
Create Date: 2026-09-04

Ships the first content pass of the no-shot rule library. Every row
is bound by the PRD §7.4 rules: statute-cited (verified against the
RAG corpus seeded in migration 013), procedural-actions only, no
strategic advice, mandatory Labourline escalation on the red-tier
patterns.

These are v0.1 rule specs. In production, every row's ``is_active``
flips only after a labour-law practitioner reviewer stamps
``reviewed_by`` and ``reviewed_at``. Migration ships them
``is_active = true`` for development and A/B measurement; a follow-up
migration will require the reviewer stamp before ``is_active``.

Idempotent: DELETE-then-INSERT per (slug, tenant_id IS NULL) so
re-running picks up any content edits.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text as _sql


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# 15 canonical clause patterns
# ---------------------------------------------------------------------------

RULES = [
    dict(
        slug="unilateral_termination_no_notice",
        name="Termination at will without notice",
        description=(
            "The company reserves the right to end the engagement at any "
            "time, without prior notice and often without a reason."
        ),
        contract_types=["aggregator", "labour"],
        default_risk_tier="red",
        citation={
            "name": "Karnataka Platform-Based Gig Workers (Social Security and Welfare) Ordinance, 2024",
            "section": "Section 14",
            "url": "https://labour.karnataka.gov.in",
        },
        topic_hint="grievance_escalation",
        generation_rules=(
            "Explanation MUST clearly state that the company can end the "
            "engagement at any moment, without warning. Do not soften "
            "with 'in some cases' or 'occasionally'. "
            "Implication MUST reference the worker's right to notice under "
            "Karnataka Ordinance 2024 Section 14 (fourteen days) if the "
            "contract is subject to Karnataka law, otherwise reference the "
            "aggregator's grievance officer requirement under the CMV Rules "
            "2024 amendment (seven-day written notice, opportunity to be "
            "heard). "
            "Action MUST be procedural: ask the platform in writing for "
            "the notice period their grievance officer will honour, and "
            "save the response. Do not tell the worker to refuse to sign "
            "or to take legal action — that is advice we do not give. "
            "Reference Rights Guide → 'Grievance escalation' in the action."
        ),
        forbidden_content=[
            "illegal", "void", "unenforceable", "you should sue",
            "grounds for a lawsuit", "you are entitled to",
        ],
        required_content=["Section 14", "notice"],
        safe_fallback={
            "explanation": "The company can end this engagement at any time without warning.",
            "implication": "You could lose access to the platform overnight, without a stated reason.",
            "action": "Ask the platform's grievance officer in writing to confirm the notice period they will honour, and save the response. See Rights Guide → 'Grievance escalation' for how to escalate if no answer arrives.",
        },
    ),
    dict(
        slug="unilateral_rate_change",
        name="Company can change per-order rates unilaterally",
        description=(
            "The platform reserves the right to revise the per-order "
            "payout at its sole discretion, at any time."
        ),
        contract_types=["aggregator"],
        default_risk_tier="red",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Fare and commission transparency",
            "url": "https://morth.nic.in",
        },
        topic_hint="minimum_wage",
        generation_rules=(
            "Explanation must state that the company can change how much "
            "the worker earns per order without asking or informing them "
            "in advance. Do not qualify this. "
            "Implication should note that under the CMV Rules 2024 "
            "amendment, aggregators must display the estimated payout "
            "at trip acceptance and cannot vary the actual payout beyond "
            "narrow prescribed reasons; a rate-change clause that does "
            "not commit to disclosure sits in tension with that. "
            "Action: keep screenshots of the payout shown at trip "
            "acceptance and the actual credit received; a documented "
            "gap is what a grievance officer or a labour officer needs "
            "to see."
        ),
        forbidden_content=[
            "illegal", "void", "you are entitled to a specific rate",
        ],
        required_content=["CMV Rules", "screenshot"],
        safe_fallback={
            "explanation": "The company can change what you earn per order without prior notice.",
            "implication": "Your income can drop suddenly and the aggregator's disclosure obligations under the CMV Rules 2024 amendment are the only backstop.",
            "action": "Screenshot the payout the app shows when you accept a trip, and the actual credit later. A documented gap is what a labour officer can act on.",
        },
    ),
    dict(
        slug="broad_indemnification",
        name="Broad indemnification of the platform by the worker",
        description=(
            "The worker agrees to defend and indemnify the platform "
            "against any claim arising from the work, without limit."
        ),
        contract_types=["aggregator", "labour", "vendor"],
        default_risk_tier="red",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Driver welfare obligations",
            "url": "https://morth.nic.in",
        },
        topic_hint="injury_on_the_job",
        generation_rules=(
            "Explanation must state that the worker is agreeing to pay "
            "for any legal claim the company faces because of the "
            "worker's work — even injuries or damage on the job. Say "
            "this plainly. "
            "Implication: for driving and delivery work in particular, "
            "the CMV Rules 2024 amendment already places specific "
            "welfare and insurance obligations on aggregators. A "
            "sweeping indemnity clause tries to shift back onto the "
            "worker what the amendment placed on the aggregator. "
            "Action: keep a personal accident insurance policy separate "
            "from anything the platform provides, and read the platform's "
            "insurance policy document. See Rights Guide → 'Injury on "
            "the job'."
        ),
        forbidden_content=["illegal", "void", "unenforceable"],
        required_content=["insurance"],
        safe_fallback={
            "explanation": "This clause makes you responsible for any legal cost or claim that comes out of the work, without a limit.",
            "implication": "If someone is injured or property is damaged during the work, the platform can ask you to pay for it, even where the CMV Rules 2024 amendment places welfare and insurance obligations on the aggregator.",
            "action": "Read the platform's insurance policy document. If it does not cover the risks in this clause, keep a personal accident policy as backup. See Rights Guide → 'Injury on the job'.",
        },
    ),
    dict(
        slug="non_compete_beyond_engagement",
        name="Non-compete restriction beyond the engagement period",
        description=(
            "The worker is prohibited from working for competing "
            "platforms during or after the engagement."
        ),
        contract_types=["aggregator", "labour"],
        default_risk_tier="red",
        citation={
            "name": "Code on Social Security, 2020",
            "section": "Chapter I definitions",
            "url": "https://labour.gov.in/sites/default/files/ss_code_gazette.pdf",
        },
        topic_hint="contract_fairness",
        generation_rules=(
            "Explanation must state that after the engagement ends, the "
            "worker cannot join a competing platform for the specified "
            "period. Name the period if given. "
            "Implication: for platform-based gig workers recognised as "
            "a distinct category under the Code on Social Security 2020, "
            "post-engagement non-competes narrow the worker's ability "
            "to earn on other platforms — the primary income route for "
            "most workers. "
            "Action: ask the platform in writing for the geographic and "
            "time scope of the restriction and save the response. Do "
            "not state whether the clause is enforceable — that is a "
            "lawyer's judgement, not ours."
        ),
        forbidden_content=[
            "illegal", "void", "unenforceable", "you can ignore this",
            "will not hold up in court",
        ],
        required_content=["scope"],
        safe_fallback={
            "explanation": "This clause restricts you from working on competing platforms after your engagement here ends.",
            "implication": "For most platform workers, moving to another platform is how income continues after an engagement ends. A broad non-compete narrows that.",
            "action": "Ask the platform in writing for the exact geography and time scope of this restriction, and save the response. A labour officer or a lawyer at India Labourline can advise on the specifics for your situation.",
        },
    ),
    dict(
        slug="arbitration_distant_jurisdiction",
        name="Arbitration in a distant city or jurisdiction",
        description=(
            "Disputes must be resolved through arbitration in a city or "
            "state far from where the worker actually works."
        ),
        contract_types=["aggregator", "labour", "vendor"],
        default_risk_tier="red",
        citation={
            "name": "Code on Social Security, 2020",
            "section": "Chapter IX",
            "url": "https://labour.gov.in/sites/default/files/ss_code_gazette.pdf",
        },
        topic_hint="grievance_escalation",
        generation_rules=(
            "Explanation must name the city or state where disputes are "
            "to be arbitrated per the clause. Say that a worker "
            "wishing to raise a dispute would need to travel there or "
            "engage a lawyer there. "
            "Implication: this makes escalation practically expensive "
            "and can foreclose complaints even when the worker has a "
            "valid grievance. State-level welfare boards (Karnataka, "
            "Rajasthan) and the labour commissioner in the worker's own "
            "state provide alternate escalation forums that do not "
            "require the arbitration venue. "
            "Action: for any dispute, contact India Labourline "
            "(1800-419-1550) first — they can guide the correct forum "
            "for the specific complaint, which may sit outside the "
            "arbitration clause."
        ),
        forbidden_content=["illegal", "void", "unenforceable"],
        required_content=["Labourline", "1800-419-1550"],
        safe_fallback={
            "explanation": "This clause requires disputes to be arbitrated in a city or state far from where you actually work.",
            "implication": "In practice, this makes raising a formal dispute costly. State-level welfare boards and your state labour commissioner may provide alternate forums that do not require the distant venue.",
            "action": "Contact India Labourline (1800-419-1550) before starting any dispute. They can guide you to the correct forum for your specific complaint.",
        },
    ),
    dict(
        slug="waiver_of_statutory_rights",
        name="Waiver of statutory rights under labour law",
        description=(
            "The worker agrees to waive rights or claims arising under "
            "specific labour laws, or acknowledges no such rights apply."
        ),
        contract_types=["aggregator", "labour"],
        default_risk_tier="red",
        citation={
            "name": "The Code on Social Security, 2020",
            "section": "Section 113",
            "url": "https://labour.gov.in/sites/default/files/ss_code_gazette.pdf",
        },
        topic_hint="minimum_wage",
        generation_rules=(
            "Explanation must state that the worker is being asked to "
            "give up rights that a specific labour law would otherwise "
            "provide. Name the law if the clause names it. "
            "Implication: the Code on Social Security 2020, Section 113, "
            "recognises platform-based gig workers as a distinct category "
            "eligible for welfare schemes. A contract cannot generally "
            "override that statutory recognition. Do not, however, state "
            "that the clause is void or that the waiver has no effect — "
            "that is a legal conclusion. "
            "Action: keep a copy of the contract with the waiver "
            "highlighted. If a scheme benefit is denied by reference to "
            "the waiver, contact India Labourline."
        ),
        forbidden_content=[
            "illegal", "void", "unenforceable", "no effect",
            "does not apply", "cannot waive", "you can ignore",
        ],
        required_content=["Code on Social Security", "Labourline"],
        safe_fallback={
            "explanation": "This clause asks you to give up rights that a labour law would otherwise provide.",
            "implication": "The Code on Social Security 2020 recognises platform-based gig workers as a distinct category eligible for welfare schemes. If a benefit is denied by reference to a waiver in this contract, that is when India Labourline can help.",
            "action": "Keep a copy of this contract with the waiver clause highlighted. Call India Labourline at 1800-419-1550 if a scheme benefit is later denied by pointing to this clause.",
        },
    ),
    dict(
        slug="platform_can_deactivate_at_will",
        name="Platform can deactivate the worker's account at will",
        description=(
            "The platform reserves the right to deactivate or suspend "
            "the worker's account without prior notice."
        ),
        contract_types=["aggregator"],
        default_risk_tier="red",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Deactivation and re-engagement",
            "url": "https://morth.nic.in",
        },
        topic_hint="grievance_escalation",
        generation_rules=(
            "Explanation must state that the platform can suspend or "
            "close the worker's account without warning. "
            "Implication: the CMV Rules 2024 amendment requires seven "
            "days' written notice and an opportunity to be heard before "
            "deactivation, with narrow exceptions for established safety "
            "violations or fraud. A contract clause that grants "
            "unilateral deactivation sits in tension with that "
            "amendment for driving and delivery work. "
            "Action: if deactivated, ask the grievance officer in "
            "writing for the specific reason and the appeal path, and "
            "save the response. See Rights Guide → 'Grievance "
            "escalation'."
        ),
        forbidden_content=["illegal", "void", "you are entitled to reinstatement"],
        required_content=["CMV Rules", "seven days"],
        safe_fallback={
            "explanation": "The platform can close or suspend your account without prior warning.",
            "implication": "Under the CMV Rules 2024 amendment, aggregators must give seven days' written notice and an opportunity to be heard, except in cases of established safety violations or fraud.",
            "action": "If deactivated, ask the grievance officer in writing for the specific reason and the appeal path. Save the response. See Rights Guide → 'Grievance escalation'.",
        },
    ),
    dict(
        slug="exclusivity_clause",
        name="Exclusivity restricting work on other platforms",
        description=(
            "The worker cannot register with, or work on, competing "
            "platforms during the engagement."
        ),
        contract_types=["aggregator"],
        default_risk_tier="amber",
        citation={
            "name": "Rajasthan Platform Based Gig Workers (Registration and Welfare) Act, 2023",
            "section": "Section 3",
            "url": "https://labour.rajasthan.gov.in",
        },
        topic_hint="contract_fairness",
        generation_rules=(
            "Explanation must state that during the engagement, the "
            "worker cannot work on competing platforms. "
            "Implication: the Rajasthan Platform-Based Gig Workers Act "
            "2023 Section 3 explicitly provides that a worker's "
            "registration under the Act does not depend on the number "
            "of platforms they are engaged on — the statute assumes "
            "multi-platform work. An exclusivity clause narrows a "
            "worker's earning options and reduces their negotiating "
            "position on this platform. "
            "Action: read the clause carefully before signing. If work "
            "is inconsistent (some days no orders), a broad exclusivity "
            "may mean lower total income than it appears. See Rights "
            "Guide → 'Contract fairness'."
        ),
        forbidden_content=["illegal", "void"],
        required_content=["multi-platform"],
        safe_fallback={
            "explanation": "During this engagement, you cannot work on competing platforms.",
            "implication": "Multi-platform work is common and the Rajasthan Gig Workers Act 2023 explicitly assumes it. An exclusivity clause narrows your earning options.",
            "action": "Before signing, think about whether work on this platform alone is enough. If it isn't, ask for the clause to be softened or removed. See Rights Guide → 'Contract fairness'.",
        },
    ),
    dict(
        slug="insurance_paid_by_worker",
        name="Worker bears the cost of insurance",
        description=(
            "The worker is required to obtain and maintain their own "
            "insurance for their vehicle or the work performed."
        ),
        contract_types=["aggregator", "rental"],
        default_risk_tier="amber",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Insurance",
            "url": "https://morth.nic.in",
        },
        topic_hint="injury_on_the_job",
        generation_rules=(
            "Explanation must state that the worker must arrange and pay "
            "for their own insurance policy. Name the type of insurance "
            "if the clause specifies. "
            "Implication: the CMV Rules 2024 amendment requires "
            "aggregators to obtain, at their cost, health insurance "
            "(minimum Rs 5 lakh), term insurance (minimum Rs 10 lakh), "
            "and accident insurance for driver-partners. A clause that "
            "pushes the cost back to the worker for these policies sits "
            "in tension with the amendment. "
            "Action: ask the platform for the policy documents for the "
            "insurance the platform itself is required to provide under "
            "the CMV Rules 2024 amendment. Keep a copy."
        ),
        forbidden_content=["illegal", "you should refuse"],
        required_content=["policy document"],
        safe_fallback={
            "explanation": "You are required to arrange and pay for insurance for the work.",
            "implication": "Under the CMV Rules 2024 amendment, aggregators must provide health, term, and accident insurance for driver-partners at their own cost. A clause pushing insurance cost onto you may not cover all of that.",
            "action": "Ask the platform for the policy documents for the insurance they are required to provide under the CMV Rules 2024 amendment. Save copies. See Rights Guide → 'Injury on the job'.",
        },
    ),
    dict(
        slug="no_employer_employee_relationship",
        name="Independent contractor framing — no employment relationship",
        description=(
            "The contract explicitly states that no employer-employee "
            "relationship is created."
        ),
        contract_types=["aggregator"],
        default_risk_tier="amber",
        citation={
            "name": "The Code on Social Security, 2020",
            "section": "Section 113",
            "url": "https://labour.gov.in/sites/default/files/ss_code_gazette.pdf",
        },
        topic_hint="minimum_wage",
        generation_rules=(
            "Explanation must state that the contract is framed as an "
            "independent-contractor arrangement — no employer, no "
            "employee. "
            "Implication: the Code on Social Security 2020 (Section 113) "
            "created a distinct category of 'platform-based gig worker' "
            "precisely because the employer-employee frame does not fit. "
            "Recognition under Section 113 gives access to welfare "
            "schemes independent of the contractual framing. Do not "
            "state that the contract's framing is 'wrong' — the framing "
            "is a legal characterisation being litigated. "
            "Action: register on e-Shram (free, at eshram.gov.in). "
            "Registration is a prerequisite for most welfare-scheme "
            "eligibility and does not depend on the contract's "
            "employment framing. See Rights Guide → 'e-Shram "
            "registration'."
        ),
        forbidden_content=[
            "illegal", "void", "the platform is wrong",
            "you are actually an employee", "misclassification",
        ],
        required_content=["e-Shram", "Section 113"],
        safe_fallback={
            "explanation": "The contract is framed as an independent-contractor arrangement, so no employer-employee relationship is created.",
            "implication": "The Code on Social Security 2020 (Section 113) recognises platform-based gig workers as a distinct category, giving access to welfare schemes independent of the contractual framing.",
            "action": "Register on e-Shram (free, at eshram.gov.in). Registration unlocks eligibility for welfare schemes and does not depend on the contract's framing. See Rights Guide → 'e-Shram registration'.",
        },
    ),
    dict(
        slug="payment_schedule_defined",
        name="Payment schedule is clearly defined",
        description=(
            "The contract specifies when payments will be made "
            "(weekly, bi-weekly, monthly), with a defined method."
        ),
        contract_types=["aggregator", "labour"],
        default_risk_tier="green",
        citation={"name": None, "section": None, "url": None},
        topic_hint=None,
        generation_rules=(
            "Explanation must state that the contract commits to a "
            "specific payment schedule (name the frequency and method). "
            "Implication: a defined payment schedule is a favourable "
            "term. It creates a documented expectation that a labour "
            "officer or grievance authority can enforce if payments do "
            "not arrive as promised. "
            "Action: no immediate action; note the schedule for future "
            "reference. If a payment is missed, the defined schedule is "
            "evidence you can point to."
        ),
        forbidden_content=[],
        required_content=[],
        safe_fallback={
            "explanation": "The contract commits to a specific payment schedule and method.",
            "implication": "A defined payment schedule is favourable — it creates a documented expectation you can point to if payments do not arrive as promised.",
            "action": None,
        },
    ),
    dict(
        slug="platform_insurance_provided",
        name="Platform provides insurance cover",
        description=(
            "The platform commits to providing insurance (accident, "
            "health, term) for the worker."
        ),
        contract_types=["aggregator"],
        default_risk_tier="green",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Insurance",
            "url": "https://morth.nic.in",
        },
        topic_hint="injury_on_the_job",
        generation_rules=(
            "Explanation must state that the platform provides insurance "
            "cover. Name the type and any sum insured if specified. "
            "Implication: the CMV Rules 2024 amendment requires "
            "aggregators to provide health insurance (minimum Rs 5 lakh), "
            "term (minimum Rs 10 lakh), and accident cover at their own "
            "cost. A contract that names these commitments is aligned "
            "with the amendment. Confirm the amounts match the "
            "regulatory floor. "
            "Action: ask for a copy of each policy document. Read the "
            "coverage terms, exclusions, and the claim process. See "
            "Rights Guide → 'Injury on the job'."
        ),
        forbidden_content=[],
        required_content=["policy document"],
        safe_fallback={
            "explanation": "The platform provides insurance cover as part of this agreement.",
            "implication": "This aligns with the CMV Rules 2024 amendment, which requires aggregators to provide health, term, and accident insurance at their cost. Confirm the amounts meet the regulatory floor.",
            "action": "Ask for a copy of each insurance policy document. Read the coverage terms, exclusions, and the claim process. See Rights Guide → 'Injury on the job'.",
        },
    ),
    dict(
        slug="grievance_channel_defined",
        name="Grievance channel defined with contact details",
        description=(
            "The contract names a grievance officer or channel and "
            "specifies the contact details."
        ),
        contract_types=["aggregator", "labour"],
        default_risk_tier="green",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Grievance redressal",
            "url": "https://morth.nic.in",
        },
        topic_hint="grievance_escalation",
        generation_rules=(
            "Explanation must state that the contract names a grievance "
            "officer or channel and gives their contact details. "
            "Implication: a defined grievance channel is favourable — "
            "the CMV Rules 2024 amendment requires aggregators to "
            "designate a Grievance Redressal Officer and to acknowledge "
            "complaints within twenty-four hours and resolve within "
            "fifteen days. "
            "Action: save the contact details in a place you can find "
            "easily. If a payment, safety, or deactivation issue arises, "
            "this is where the paper trail starts."
        ),
        forbidden_content=[],
        required_content=["Grievance Redressal Officer"],
        safe_fallback={
            "explanation": "The contract names a grievance channel and gives the contact details.",
            "implication": "This is favourable. Under the CMV Rules 2024 amendment, aggregators must acknowledge complaints within twenty-four hours and resolve within fifteen days.",
            "action": "Save the grievance officer's contact details somewhere you can find them. If a payment, safety, or deactivation issue arises, that is where the paper trail starts.",
        },
    ),
    dict(
        slug="working_hour_cap_defined",
        name="Working-hour cap or rest requirement defined",
        description=(
            "The contract commits to a working-hour cap or a rest "
            "requirement (twelve-hour daily cap, mandatory rest, etc.)."
        ),
        contract_types=["aggregator"],
        default_risk_tier="green",
        citation={
            "name": "Central Motor Vehicles Rules — Aggregator obligations, 2024 amendment",
            "section": "Working hours",
            "url": "https://morth.nic.in",
        },
        topic_hint="injury_on_the_job",
        generation_rules=(
            "Explanation must state that the contract commits to a "
            "working-hour cap or a rest requirement. Name the exact "
            "hours if specified. "
            "Implication: the CMV Rules 2024 amendment sets a twelve-"
            "hour daily active-working-hour cap for aggregator "
            "driver-partners, with ten consecutive hours off before the "
            "next accepted request. A contract that reflects this is "
            "aligned with the amendment. "
            "Action: keep track of active hours during a shift. If the "
            "app allows more work than the cap permits, that is worth "
            "raising with the grievance officer."
        ),
        forbidden_content=[],
        required_content=["twelve"],
        safe_fallback={
            "explanation": "The contract commits to a working-hour cap or rest requirement for the worker.",
            "implication": "The CMV Rules 2024 amendment sets a twelve-hour daily cap with ten hours off before the next work request. A contract reflecting this is aligned.",
            "action": "Keep track of your active hours. If the app allows more work than the cap permits, raise it with the grievance officer.",
        },
    ),
    dict(
        slug="data_sharing_consent",
        name="Consent to data sharing with the platform",
        description=(
            "The worker consents to the platform collecting and "
            "processing personal and work data."
        ),
        contract_types=["aggregator", "labour", "vendor"],
        default_risk_tier="amber",
        citation={"name": None, "section": None, "url": None},
        topic_hint="contract_fairness",
        generation_rules=(
            "Explanation must state that the worker is agreeing to let "
            "the platform collect, use, and share personal and work "
            "data. Name any specific categories the clause mentions "
            "(location, earnings, ratings, phone number). "
            "Implication: data sharing is a routine feature of platform "
            "work, but the scope varies. A broad clause allows sharing "
            "with third parties for purposes the worker cannot easily "
            "predict. Be aware of what is being agreed to. "
            "Action: ask the platform for the categories of data they "
            "share with third parties, and for the purposes. If a "
            "privacy policy is referenced, keep the URL."
        ),
        forbidden_content=["illegal", "you must refuse"],
        required_content=["privacy policy"],
        safe_fallback={
            "explanation": "You are agreeing to let the platform collect, use, and share your data (location, work history, phone number, ratings).",
            "implication": "Data sharing is routine on platforms, but the scope varies. A broad clause allows sharing with third parties for purposes you cannot easily predict.",
            "action": "Ask the platform for the categories of data they share with third parties and the purposes. If a privacy policy is referenced, keep the URL.",
        },
    ),
]


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

_DELETE = """
    DELETE FROM clause_rules
     WHERE slug = :slug AND tenant_id IS NULL;
"""

_INSERT = """
    INSERT INTO clause_rules
        (slug, name, description, contract_types, default_risk_tier,
         citation, topic_hint, generation_rules, forbidden_content,
         required_content, safe_fallback, is_active, version)
    VALUES
        (:slug, :name, :description, CAST(:contract_types AS jsonb),
         :risk, CAST(:citation AS jsonb), :topic_hint,
         :generation_rules, CAST(:forbidden AS jsonb),
         CAST(:required AS jsonb), CAST(:safe_fallback AS jsonb),
         true, 1);
"""


def upgrade() -> None:
    bind = op.get_bind()
    for rule in RULES:
        bind.execute(_sql(_DELETE), {"slug": rule["slug"]})
        bind.execute(_sql(_INSERT), {
            "slug": rule["slug"],
            "name": rule["name"],
            "description": rule["description"],
            "contract_types": json.dumps(rule["contract_types"]),
            "risk": rule["default_risk_tier"],
            "citation": json.dumps(rule["citation"]),
            "topic_hint": rule["topic_hint"],
            "generation_rules": rule["generation_rules"],
            "forbidden": json.dumps(rule["forbidden_content"]),
            "required": json.dumps(rule["required_content"]),
            "safe_fallback": json.dumps(rule["safe_fallback"]),
        })


def downgrade() -> None:
    bind = op.get_bind()
    for rule in RULES:
        bind.execute(_sql("DELETE FROM clause_rules WHERE slug = :slug AND tenant_id IS NULL"),
                     {"slug": rule["slug"]})
