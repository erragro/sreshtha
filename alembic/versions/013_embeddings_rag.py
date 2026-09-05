"""embeddings table + pgvector extension for RAG retrieval

Revision ID: 013
Revises: 012
Create Date: 2026-09-04

Introduces the vector store that Stage 2 (annotate) will retrieve
against for statute-grounded citations, and that a future chatbot RAG
will query for Rights Guide fact-card retrieval.

Design decisions (see PRD Appendix E):
- **Embedding model:** OpenAI ``text-embedding-3-large``, dimension-
  reduced to **1024** via the Matryoshka Representation Learning path
  (``dimensions=1024`` on the embed call). Higher legal-domain retrieval
  quality than ``text-embedding-3-small`` at smaller storage than
  full-dim large.
- **Index:** HNSW with cosine ops. Consensus across four benchmark
  sources: HNSW dominates on recall and p99 latency for corpora under
  1M rows at negligible memory penalty (~40 MB for the seed statute
  corpus).
- **`source_type` taxonomy:** kept as free string with a CHECK
  constraint so new source kinds land as a one-line migration (add
  another allowed value) rather than an enum churn. v1 kinds:
  ``statute`` (the seed corpus), ``fact_card`` (Rights Guide RAG,
  post-launch), ``complaint_template`` (post-launch), ``idiom``
  (post-launch).
- **`tenant_id` scoping:** matches every other content table. NULL =
  shared corpus visible to every tenant. A tenant can add its own
  chunks with ``tenant_id=<uuid>`` and queries return the union of
  ``tenant_id IS NULL`` and ``tenant_id = <caller>``.

Idempotent: enables the extension with ``IF NOT EXISTS`` so re-running
the upgrade is safe. Downgrade drops the table but leaves the
extension installed (dropping the extension would cascade to any
other future consumer).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Allowed source kinds. Enforced by a CHECK constraint so new kinds add
# via a one-line migration rather than an enum-type churn.
SOURCE_TYPES = ("statute", "fact_card", "complaint_template", "idiom")
_SOURCE_CHECK = "source_type IN (" + ", ".join(f"'{s}'" for s in SOURCE_TYPES) + ")"

# Dimension of the embedding column. Matched to the value we pass to
# OpenAI's ``text-embedding-3-large`` via the ``dimensions=`` param.
# See scripts/ingest_statute_corpus.py for the enforcement point.
EMBEDDING_DIMS = 1024


# ---------------------------------------------------------------------------
# Upgrade / downgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ---------------- pgvector extension ----------------
    # The pgvector/pgvector:pg16 Docker image includes the extension;
    # on a plain postgres:16-alpine you'd need to install it separately.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ---------------- embeddings ----------------
    op.create_table(
        "embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Kind of source this chunk came from. Kept as a small string
        # with a CHECK constraint rather than an enum type.
        sa.Column("source_type", sa.String(length=40), nullable=False),
        # Stable identifier for the source document. For statutes this
        # is a slug like ``code_on_social_security_2020``; for
        # fact_cards it will be the topic_key.
        sa.Column("source_id", sa.String(length=120), nullable=False),
        # Free-form JSONB metadata about the chunk. For statute chunks:
        # {statute_name, year, section_number, chunk_index, url}. For
        # fact_cards later: {topic_key, language, card_id}.
        sa.Column(
            "source_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # The actual chunk text — returned verbatim to the retrieval
        # caller so Stage 2's prompt can inject it.
        sa.Column("chunk_text", sa.Text(), nullable=False),
        # The vector column. ``vector(N)`` is the pgvector type; N must
        # match ``EMBEDDING_DIMS`` exactly (pgvector rejects any other
        # length at insert time).
        sa.Column(
            "embedding",
            postgresql.ARRAY(sa.Float),  # placeholder — replaced below
            nullable=False,
        ),
        # Multi-tenant scoping. NULL = shared corpus.
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(_SOURCE_CHECK, name="ck_embeddings_source_type"),
    )

    # SQLAlchemy's dialect doesn't know about the pgvector ``vector(N)``
    # type. Rewrite the column to the correct pgvector type in raw SQL.
    op.execute(
        "ALTER TABLE embeddings "
        "ALTER COLUMN embedding TYPE vector(" + str(EMBEDDING_DIMS) + ") "
        "USING embedding::vector"
    )

    # ---------------- indexes ----------------
    # HNSW cosine index for semantic similarity queries. `m=16` and
    # `ef_construction=64` are pgvector's defaults; these tune well for
    # corpora up to ~1M rows.
    op.execute(
        "CREATE INDEX embeddings_hnsw_cosine "
        "ON embeddings USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.create_index(
        "ix_embeddings_source",
        "embeddings",
        ["source_type", "source_id"],
    )
    op.create_index("ix_embeddings_tenant", "embeddings", ["tenant_id"])
    op.execute(
        "CREATE INDEX ix_embeddings_active "
        "ON embeddings (is_active) WHERE is_active = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_embeddings_active")
    op.drop_index("ix_embeddings_tenant", table_name="embeddings")
    op.drop_index("ix_embeddings_source", table_name="embeddings")
    op.execute("DROP INDEX IF EXISTS embeddings_hnsw_cosine")
    op.drop_table("embeddings")
    # Deliberately NOT dropping the extension — it may be used by
    # future consumers, and installing it isn't free (it does IO).
