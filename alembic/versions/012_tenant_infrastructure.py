"""tenant infrastructure: tenants + memberships + FKs for partner onboarding

Revision ID: 012
Revises: 011
Create Date: 2026-08-24

Introduces the multi-tenant scaffolding a partner (welfare board,
labour union, insurer, NGO) needs to run a self-hosted or shared
Sreshtha deployment.

Design principles:
- ``tenant_id IS NULL`` on any content row keeps meaning "shared across
  all tenants" — this preserves the seed data from earlier migrations.
- A tenant's own overrides are inserted with ``tenant_id = <tenant.id>``
  and take precedence in service reads.
- Users may belong to multiple tenants via ``tenant_memberships``
  (many-to-many). ``users.default_tenant_id`` tracks the tenant the
  user's session lands in by default (nullable so existing users are
  unaffected).
- ``uploaded_contracts`` gets an explicit ``tenant_id`` FK because a
  worker's contract belongs to a tenant, not to the shared library.
- All existing tables that already had a nullable ``tenant_id`` column
  now gain a real FK constraint to ``tenants(id)`` so integrity is
  enforced.
- Deleting a tenant cascades to memberships + worker-owned content
  (contracts). Tenant-scoped library content (idioms, fact cards,
  schemes, complaint templates) sets tenant_id back to NULL on tenant
  delete so it falls back to the shared library rather than
  disappearing.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Kinds a tenant can be. Free-form-ish string with a CHECK constraint —
# adding a new kind is a one-line migration, not an enum type churn.
TENANT_KINDS = ("welfare_board", "union", "sponsor", "ngo", "internal", "other")
_KIND_CHECK = "kind IN (" + ", ".join(f"'{k}'" for k in TENANT_KINDS) + ")"

TENANT_STATUSES = ("active", "pending", "suspended", "archived")
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s}'" for s in TENANT_STATUSES) + ")"

# Role on a tenant. `owner` is billing/legal owner; `admin` can manage
# users + settings; `editor` edits library content; `member` reads.
MEMBER_ROLES = ("owner", "admin", "editor", "member")
_ROLE_CHECK = "role IN (" + ", ".join(f"'{r}'" for r in MEMBER_ROLES) + ")"


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ---------------- tenants ----------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # URL-safe slug used as an addressable identifier. Enforced
        # lowercase-alnum-hyphen at the application layer; a CHECK
        # regex here would trip Postgres < 12 compatibility.
        sa.Column("slug", sa.String(length=60), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default=sa.text("'active'")),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("contact_phone", sa.String(length=40), nullable=True),
        # White-label branding: {logo_url, primary_color, tagline,
        # native_name}. Rendered by the frontend when a user's session
        # tenant is set. Free-form JSON so partners can extend without
        # a schema break.
        sa.Column("branding",
                  postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        # Per-tenant feature flags + limits. Currently:
        # {"rate_limit_contracts_per_day": 100, "modules_enabled":
        # ["contract_reader", "rights_guide"], ...}
        sa.Column("config",
                  postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(_KIND_CHECK, name="ck_tenants_kind"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_tenants_status"),
    )
    op.create_index("ix_tenants_kind_status", "tenants", ["kind", "status"])

    # ---------------- tenant_memberships ----------------
    op.create_table(
        "tenant_memberships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(_ROLE_CHECK, name="ck_tenant_memberships_role"),
        sa.UniqueConstraint("tenant_id", "user_id",
                            name="uq_tenant_memberships_tenant_user"),
    )
    op.create_index("ix_tenant_memberships_user", "tenant_memberships", ["user_id"])
    op.create_index("ix_tenant_memberships_tenant", "tenant_memberships", ["tenant_id"])

    # ---------------- users.default_tenant_id ----------------
    op.add_column(
        "users",
        sa.Column(
            "default_tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_users_default_tenant", "users", ["default_tenant_id"])

    # ---------------- uploaded_contracts.tenant_id ----------------
    # Worker documents are tenant-owned. A contract uploaded through
    # the Karnataka welfare board deployment stays inside that tenant.
    op.add_column(
        "uploaded_contracts",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_uploaded_contracts_tenant", "uploaded_contracts", ["tenant_id"])

    # ---------------- FKs on existing content tables ----------------
    # These tables already had a nullable tenant_id column from earlier
    # migrations — add real FK constraints now that tenants exists.
    # ON DELETE SET NULL preserves the row (falls back to shared library)
    # rather than deleting curated content when a tenant is archived.
    for table_name in (
        "fact_cards",
        "schemes",
        "complaint_templates",
        "idiom_library",
    ):
        op.create_foreign_key(
            f"fk_{table_name}_tenant",
            table_name,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="SET NULL",
        )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    for table_name in (
        "fact_cards",
        "schemes",
        "complaint_templates",
        "idiom_library",
    ):
        op.drop_constraint(f"fk_{table_name}_tenant", table_name, type_="foreignkey")

    op.drop_index("ix_uploaded_contracts_tenant", table_name="uploaded_contracts")
    op.drop_column("uploaded_contracts", "tenant_id")

    op.drop_index("ix_users_default_tenant", table_name="users")
    op.drop_column("users", "default_tenant_id")

    op.drop_index("ix_tenant_memberships_tenant", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_user", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")

    op.drop_index("ix_tenants_kind_status", table_name="tenants")
    op.drop_table("tenants")
