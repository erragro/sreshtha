"""Similarity search over the ``embeddings`` table.

Public API:

- ``retrieve_context(query_text, *, source_type, k, threshold,
  tenant_id)`` — embed the query, run pgvector's cosine-distance
  query, return the top-k rows whose similarity meets the threshold.
  Similarity is ``1 - distance``; threshold is a floor on similarity
  (so 0.75 means "at least 75% cosine similar").

- ``format_for_stage2(rows)`` — render retrieved chunks into a prompt-
  friendly block that Stage 2's user message can splice in. Preserves
  source metadata so the annotator can cite what it saw.

The tenant filter mirrors the pattern from other content queries:
NULL-tenant rows are the shared corpus and are always visible; a
caller passing a specific tenant_id also sees that tenant's rows.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text as _sql
from sqlalchemy.orm import Session

from app.retrieval.embedder import DEFAULT_DIMENSIONS, DEFAULT_MODEL, embed_one


logger = logging.getLogger(__name__)


DEFAULT_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.35   # cosine similarity in [0, 1]
# NOTE: for OpenAI text-embedding-3-* the mean cosine similarity of
# unrelated pairs is ~0.05-0.15, and topically-related pairs cluster
# around 0.35-0.55. A 0.75 threshold as originally scoped in the PRD
# was too aggressive for these embeddings and drops all matches for
# most real clauses. 0.35 gives sensible retrieval with the current
# corpus size while still filtering out clearly-unrelated statutes.


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_text: str
    source_type: str
    source_id: str
    metadata: dict[str, Any]
    similarity: float


def retrieve_context(
    db: Session,
    *,
    query_text: str,
    source_type: str = "statute",
    k: int = DEFAULT_K,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    tenant_id: str | None = None,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[RetrievedChunk]:
    """Top-k similarity search filtered by ``source_type`` and tenant.

    Returns rows in decreasing similarity, up to ``k`` items, only
    where ``similarity >= threshold``. Empty result is normal — the
    caller decides whether that means "cite nothing" or "fall back to
    a broader retrieval".
    """
    if not query_text or not query_text.strip():
        return []

    # 1. Embed the query.
    query_vec = embed_one(query_text, model=model, dimensions=dimensions)

    # pgvector accepts a vector literal in the form "[v0,v1,...]" via
    # explicit cast. SQLAlchemy binds it as text.
    vec_literal = "[" + ",".join(f"{x:.7f}" for x in query_vec) + "]"

    # 2. Query. Bind tenant condition as literal SQL because a NULL
    # value in a bound param won't match ``tenant_id IS NULL`` — we
    # want (tenant_id IS NULL OR tenant_id = :tenant) semantics.
    sql = """
        SELECT chunk_text,
               source_type,
               source_id,
               source_metadata,
               1 - (embedding <=> CAST(:vec AS vector)) AS similarity
          FROM embeddings
         WHERE is_active = true
           AND source_type = :source_type
           AND (tenant_id IS NULL {tenant_clause})
           AND 1 - (embedding <=> CAST(:vec AS vector)) >= :threshold
      ORDER BY embedding <=> CAST(:vec AS vector)
         LIMIT :k
    """
    params: dict[str, Any] = {
        "vec": vec_literal,
        "source_type": source_type,
        "threshold": threshold,
        "k": k,
    }
    if tenant_id:
        tenant_clause = "OR tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    else:
        tenant_clause = ""

    rows = db.execute(_sql(sql.format(tenant_clause=tenant_clause)), params).all()

    return [
        RetrievedChunk(
            chunk_text=r.chunk_text,
            source_type=r.source_type,
            source_id=r.source_id,
            metadata=r.source_metadata or {},
            similarity=float(r.similarity),
        )
        for r in rows
    ]


def format_for_stage2(rows: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a prompt block. Kept simple and
    citation-anchored — each chunk shows its statute name, section
    number, and URL so the LLM can quote the exact source when it
    fills the ``citation`` field.

    Empty list → an explicit "no matches" marker so the prompt tells
    the annotator to emit ``citation: null`` rather than invent one."""
    if not rows:
        return (
            "STATUTE CORPUS: no matches above the retrieval similarity "
            "threshold for this batch. Emit citation: null on each "
            "clause unless you can point to a section from memory that "
            "is universally uncontested (e.g. Code on Social Security "
            "2020, s.113 for gig-worker recognition)."
        )

    out = [
        "STATUTE CORPUS (top-{k} retrieved chunks; cite these when "
        "assigning a citation to a clause):".format(k=len(rows))
    ]
    for i, r in enumerate(rows, start=1):
        statute_name = r.metadata.get("statute_name", r.source_id)
        section_number = r.metadata.get("section_number")
        url = r.metadata.get("url")
        head_bits = [f"{i}.", statute_name]
        if section_number:
            head_bits.append(f"(Section {section_number})")
        head_bits.append(f"[similarity {r.similarity:.2f}]")
        out.append(" ".join(head_bits))
        if url:
            out.append(f"   URL: {url}")
        # Indent the chunk body two spaces for readability.
        for line in r.chunk_text.splitlines():
            out.append("   " + line)
        out.append("")
    return "\n".join(out).rstrip()
