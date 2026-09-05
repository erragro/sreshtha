"""clause_rules — no-shot rule library for Contract Reader Stage 3

Revision ID: 014
Revises: 013
Create Date: 2026-09-04

Introduces the ``clause_rules`` table that Stage 3 uses to generate
worker-facing explanations under strict, per-pattern rule specs. Each
row is one clause pattern (``unilateral_termination_no_notice``,
``broad_indemnification``, …) with:

- ``generation_rules``  100–200-word English rule spec — what MUST be
                        said in the worker-facing output, what MUST
                        NOT be said, when to reference which statute
                        section.
- ``forbidden_content`` JSONB array of blocklist phrases the validator
                        rewrites or blocks.
- ``required_content``  JSONB array of anchor phrases the output must
                        contain (validator flags omission).
- ``citation``          Structured statute reference verified against
                        the RAG corpus (name, section, url).
- ``topic_hint``        Rights Guide fact-card slug for cross-linking.
- ``safe_fallback``     Canonical explanation used when the LLM output
                        fails validation twice — never null so the
                        worker always sees something intelligible.
- Version, reviewed_by, reviewed_at, is_active, tenant_id.

Design choices (see PRD §7.4 and Appendix E):
- No exemplar corpus. Rules are enough for legal patterns.
- Every edit bumps ``version`` and stamps ``reviewed_by`` / ``reviewed_at``.
- ``ON DELETE SET NULL`` on ``tenant_id`` — a tenant's overrides revert
  to shared library on tenant archive, not disappear.
- Uniqueness enforced on ``(slug, tenant_id)`` so a tenant can override
  a shared slug with its own row.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RISK_TIERS = ("red", "amber", "green")
_RISK_CHECK = "default_risk_tier IN (" + ", ".join(f"'{r}'" for r in RISK_TIERS) + ")"


# ---------------------------------------------------------------------------
# Upgrade / downgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    op.create_table(
        "clause_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # URL-safe slug shared across all versions of the same pattern.
        # e.g. "unilateral_termination_no_notice".
        sa.Column("slug", sa.String(length=80), nullable=False),
        # Human-readable name shown in the admin surface (Conversation Studio
        # extension) and in the classifier's prompt at runtime.
        sa.Column("name", sa.String(length=200), nullable=False),
        # 1-2 sentence description for the admin surface; also fed to the
        # fast classifier as part of the taxonomy prompt so it knows
        # what each slug means.
        sa.Column("description", sa.Text(), nullable=False),
        # Array of contract types this rule applies to. Empty means all.
        # e.g. ["aggregator", "labour"].
        sa.Column(
            "contract_types",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("default_risk_tier", sa.String(length=10), nullable=False),
        # Structured citation matching the shape Stage 2 emits — this row's
        # citation is the one Stage 2 will confirm-and-cite when this
        # pattern is matched.
        sa.Column(
            "citation",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Rights Guide fact-card slug for cross-linking in Stage 3
        # output. Nullable.
        sa.Column("topic_hint", sa.String(length=80), nullable=True),
        # The rule spec the generator LLM reads at inference. Free text,
        # 100–200 words in English. Reviewed by a labour-law practitioner
        # before is_active flips to true.
        sa.Column("generation_rules", sa.Text(), nullable=False),
        # Array of strings the output must NOT contain (case-insensitive
        # substring match). e.g. ["illegal", "you should sue"].
        sa.Column(
            "forbidden_content",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Array of strings the output MUST contain at least one of
        # (case-insensitive substring match). e.g. ["Section 113",
        # "Labourline"]. Empty = no required content.
        sa.Column(
            "required_content",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # Canonical safe fallback shown when the LLM output fails
        # validation twice. Never null so worker always sees something.
        # Shape: {"explanation": "...", "implication": "...", "action": "..."}
        sa.Column(
            "safe_fallback",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Versioning + provenance.
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(_RISK_CHECK, name="ck_clause_rules_risk_tier"),
        sa.UniqueConstraint("slug", "tenant_id", name="uq_clause_rules_slug_tenant"),
    )
    op.create_index("ix_clause_rules_slug", "clause_rules", ["slug"])
    op.create_index("ix_clause_rules_active", "clause_rules", ["is_active"])
    op.create_index("ix_clause_rules_tenant", "clause_rules", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_clause_rules_tenant", table_name="clause_rules")
    op.drop_index("ix_clause_rules_active", table_name="clause_rules")
    op.drop_index("ix_clause_rules_slug", table_name="clause_rules")
    op.drop_table("clause_rules")
