"""Stage 2 — Research.

Takes the structured clauses from Stage 1 and annotates each with:
  - risk: red (adverse to the worker), amber (worth knowing), green (favourable)
  - statute: the Indian law reference that governs this clause, if any
  - note: a short (1-2 sentence) explanation of why the clause got its risk tier

Stays in English — the reasoning about Indian labour law is easier to
control in one canonical language, and Stage 3 handles the translation
to the worker's UI language separately. Kept generative (LLM) rather
than rule-based because clause language varies enormously; a rules
engine would need thousands of patterns to cover the corpus.

Idempotent: re-running on the same Stage 1 output produces the same
schema, though the annotation text will vary slightly across runs.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.l2_agents.llm_provider import get_provider


logger = logging.getLogger(__name__)


_ALLOWED_RISK = {"red", "amber", "green"}


_SYSTEM = """You are analysing an Indian gig-worker contract clause by clause against Indian labour law.

Statutes and frameworks you may cite (each with the canonical URL to use):
- Code on Social Security, 2020 — https://labour.gov.in/sites/default/files/ss_code_gazette.pdf
- Karnataka Platform-Based Gig Workers (Social Security and Welfare) Ordinance, 2024 — https://labour.karnataka.gov.in
- Rajasthan Platform Based Gig Workers (Registration and Welfare) Act, 2023 — https://labour.rajasthan.gov.in
- Central Motor Vehicles Rules amendment (aggregator obligations), 2024 — https://morth.nic.in
- Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013 (POSH) — https://wcd.nic.in
- Fairwork India annual ratings — https://fair.work/en/ratings/india/
- Industrial Disputes Act, 1947 (Section 2A: individual dispute recourse) — https://labour.gov.in
- Consumer Protection Act, 2019 (alternate route for transaction disputes) — https://consumeraffairs.nic.in
- Payment of Wages Act, 1936 (wage-theft escalation ladder) — https://labour.gov.in

Risk tiers:
- red    Adverse to the worker: unilateral deactivation without notice,
         opaque per-order pricing, broad indemnification of the platform,
         waiver of statutory rights, non-compete, one-way arbitration in
         another jurisdiction.
- amber  Worth knowing but not necessarily unfair: exclusivity, data-sharing
         consent, dispute-resolution requirements, background verification,
         vehicle-condition requirements.
- green  Favourable or protective: insurance cover, defined payment schedules,
         injury compensation, grievance channels, explicit rest-hour limits.

Contract-type-specific reasoning (the input tells you which):
- aggregator  Focus on Motor Vehicles Rules 2024 amendment (delivery/cab),
              Code on Social Security 2020 §113-114 recognition, state gig
              welfare board rules (Karnataka, Rajasthan). Aggregator
              contracts almost never carry EPFO/ESIC coverage — flag when
              they claim to.
- labour      Full employment law applies: Industrial Disputes Act 1947
              §2A, Payment of Wages Act 1936, EPFO/ESIC statutory
              contributions. Missing statutory benefits are usually red.
- vendor      Business-to-business — worker-protection lens is weaker.
              Focus instead on Consumer Protection Act, dispute forums,
              and payment reliability.
- rental      Motor Vehicles Rules, vehicle liability, insurance passthrough.
              Deposit terms and depreciation clauses are common red flags.
- unknown     Fall back to the general framework above.

Return ONLY a JSON object with this shape (no prose, no code fences):

{
  "annotations": [
    {
      "clause_id": "<matches an id from the input clauses>",
      "risk": "red" | "amber" | "green",
      "citation": {
        "name": "<statute or scheme name, e.g. 'Code on Social Security, 2020', or null>",
        "section": "<section reference, e.g. 'Section 113', 'Chapter IX', or null>",
        "url": "<canonical URL from the list above, or null>"
      },
      "note": "<one to two sentence English explanation of the risk assessment>",
      "topic_hint": "<Rights Guide topic slug that this clause relates to: 'minimum_wage' | 'injury_on_the_job' | 'grievance_escalation' | 'e_shram_registration' | 'contract_fairness' | null>"
    },
    ...
  ]
}

Every input clause must have a corresponding annotation — do not skip clauses.
If a clause is boilerplate (definitions, signatures, notices) mark it green
with citation set to all-null and a brief note.
If no statute applies, set every field of citation to null (do not invent
citations).
If a clause relates to a Rights Guide topic (minimum wage, injury, grievance
escalation, e-Shram registration, contract fairness), populate topic_hint.
"""


from concurrent.futures import ThreadPoolExecutor, as_completed

from app.db import SessionLocal
from app.retrieval.retriever import format_for_stage2, retrieve_context


# Chunked parallelism knobs — matches Stage 3's shape so operations
# folks see one mental model across the pipeline.
_STAGE2_CHUNK_SIZE = 5
_STAGE2_MAX_WORKERS = 6
# Per-clause RAG retrieval depth. Small on purpose — each chunk has
# five clauses, so five clauses × three chunks = 15 chunks in the
# annotator prompt. Bigger k dilutes signal and can push over gpt-4o's
# comfortable context.
_RAG_K_PER_CLAUSE = 3
_RAG_THRESHOLD = 0.30

# State welfare laws are useful context, but they do not apply merely because
# a contract is for gig work. Keep the mapping deliberately small and explicit
# so a model cannot present a familiar state statute as nationwide law.
_STATE_SPECIFIC_CITATIONS = {
    "karnataka platform-based gig workers": "karnataka",
    "rajasthan platform based gig workers": "rajasthan",
}


def annotate(stage_1_output: dict[str, Any]) -> dict[str, Any]:
    """Run Stage 2. `stage_1_output` is the dict Stage 1 produced.
    Reasoning is always in English regardless of contract language.

    Provider mapping (per-stage hybrid architecture):
      - Primary: OpenAI ``gpt-4o`` (role="smart") — the reasoning-heavy
        stage where 4o's advantage over mini matters.
      - RAG-grounded: statute chunks from the ``embeddings`` table
        (migration 013 corpus) are retrieved per-batch and injected
        into the annotator prompt. The annotator cites what it saw
        rather than statute numbers pulled from parametric memory.
      - Chunked parallelism: clauses batched 5 per call, run through a
        ``ThreadPoolExecutor`` of 6 workers. 30-clause contract
        finishes in ~8-12s instead of ~25-40s sequential.
    """
    clauses = stage_1_output.get("clauses") or []
    if not clauses:
        return {"annotations": [], "error": None}

    contract_type = stage_1_output.get("contract_type") or "unknown"
    metadata = stage_1_output.get("metadata") or {}
    jurisdiction = str(metadata.get("jurisdiction") or "").strip()

    # Split into batches of 5 in original order.
    chunks: list[list[dict[str, Any]]] = [
        clauses[i : i + _STAGE2_CHUNK_SIZE]
        for i in range(0, len(clauses), _STAGE2_CHUNK_SIZE)
    ]

    provider = get_provider("en", provider="openai")

    results_by_idx: dict[int, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=_STAGE2_MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                _annotate_chunk,
                provider=provider,
                contract_type=contract_type,
                jurisdiction=jurisdiction,
                clauses_chunk=chunk,
            ): idx
            for idx, chunk in enumerate(chunks)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results_by_idx[idx] = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("stage 2 chunk %d failed: %s", idx, exc)
                results_by_idx[idx] = []

    # Reassemble in original order.
    annotations: list[dict[str, Any]] = []
    for idx in range(len(chunks)):
        annotations.extend(results_by_idx.get(idx, []))

    # Backfill missing clauses so downstream always has an annotation.
    seen = {a["clause_id"] for a in annotations}
    expected_ids = {c["id"] for c in clauses}
    for cid in expected_ids - seen:
        annotations.append({
            "clause_id": cid,
            "risk": "amber",
            "citation": _null_citation(),
            "note": "This clause was not annotated. Review manually.",
            "topic_hint": None,
        })

    _remove_inapplicable_state_citations(annotations, jurisdiction)

    return {"annotations": annotations, "error": None}


def _annotate_chunk(
    *,
    provider,
    contract_type: str,
    jurisdiction: str,
    clauses_chunk: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Retrieve RAG context per clause, then run one gpt-4o call for
    the batch. Returns just the annotations list for this chunk."""

    # RAG: retrieve top-k statute chunks per clause and combine into a
    # single prompt block. Open one DB session per chunk (thread-safe).
    rag_block = ""
    with SessionLocal() as db:
        retrieved_by_clause: list[list] = []
        for clause in clauses_chunk:
            query = _rag_query_for_clause(clause)
            rows = retrieve_context(
                db,
                query_text=query,
                source_type="statute",
                k=_RAG_K_PER_CLAUSE,
                threshold=_RAG_THRESHOLD,
            )
            retrieved_by_clause.append(rows)
        # Union of retrieved chunks across the batch, deduped by
        # (source_id, section_number, chunk_index).
        seen_keys: set[tuple] = set()
        deduped = []
        for rows in retrieved_by_clause:
            for r in rows:
                key = (
                    r.source_id,
                    r.metadata.get("section_number"),
                    r.metadata.get("chunk_index"),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(r)
        # Keep only the top ~10 to bound prompt size.
        deduped.sort(key=lambda r: -r.similarity)
        rag_block = format_for_stage2(deduped[:10])

    payload = {
        "contract_type": contract_type,
        "jurisdiction": jurisdiction or None,
        "clauses": [
            {
                "id": c["id"],
                "heading": c.get("heading"),
                "section_number": c.get("section_number"),
                "text": c["text"],
            }
            for c in clauses_chunk
        ],
    }

    raw = provider.chat(
        role="smart",  # gpt-4o
        system=_SYSTEM,
        user=(
            rag_block
            + "\n\n---\n\n"
            + "Analyse each clause below and return the annotations JSON. "
            + "For every clause, either cite one of the RAG chunks above "
            + "(carrying the exact section number and URL) or set every "
            + "field of citation to null. State-specific law may be cited "
            + "only when its state exactly matches the contract jurisdiction. "
            + "For an unknown or different jurisdiction, do not cite Karnataka "
            + "or Rajasthan law; use an applicable central source or null.\n\n"
            + "Clauses to annotate:\n"
            + json.dumps(payload, indent=2)
        ),
        max_tokens=8000,
        temperature=0.1,
    )
    partial = _parse(raw, expected_ids={c["id"] for c in clauses_chunk})
    return partial.get("annotations") or []


def _rag_query_for_clause(clause: dict[str, Any]) -> str:
    """Build the retrieval query for one clause. Heading + text
    concatenated gives more signal than text alone; capped to avoid a
    query blob that dilutes the embedding."""
    heading = clause.get("heading") or ""
    text = clause.get("text") or ""
    q = (heading + ". " + text) if heading else text
    return q[:1500]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _parse(raw: str, *, expected_ids: set[str]) -> dict[str, Any]:
    if not raw or not raw.strip():
        return _empty_result("empty response from stage 2 llm", expected_ids)

    text = raw.strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("stage 2: could not parse response; raw=%r", text[:300])
        return _empty_result("could not parse stage 2 response as JSON", expected_ids)

    if not isinstance(data, dict):
        return _empty_result("stage 2 response was not an object", expected_ids)

    annotations_raw = data.get("annotations") or []
    annotations = _clean_annotations(annotations_raw)

    # Backfill any missing clauses so the downstream viewer always has
    # something to show. Missing annotations default to amber ("worth
    # knowing") with a fallback note — deliberately not green because
    # a missing annotation is the model failing to reason, not evidence
    # of harmlessness.
    seen = {a["clause_id"] for a in annotations}
    for cid in expected_ids - seen:
        annotations.append({
            "clause_id": cid,
            "risk": "amber",
            "citation": _null_citation(),
            "note": "This clause was not annotated by the analyser. Review it manually.",
            "topic_hint": None,
        })

    return {"annotations": annotations, "error": None}


_ALLOWED_TOPIC_HINTS = {
    "minimum_wage",
    "injury_on_the_job",
    "grievance_escalation",
    "e_shram_registration",
    "contract_fairness",
}


def _null_citation() -> dict[str, Any]:
    return {"name": None, "section": None, "url": None}


def _remove_inapplicable_state_citations(
    annotations: list[dict[str, Any]], jurisdiction: str,
) -> None:
    """Remove state-law citations that do not match the agreement's state.

    Prompt instructions reduce the error rate, but this deterministic guard is
    the final safety check before a legal reference reaches a worker.
    """
    normalised_jurisdiction = jurisdiction.lower()
    for annotation in annotations:
        citation = annotation.get("citation") or {}
        name = str(citation.get("name") or "").lower()
        required_state = next(
            (
                state
                for marker, state in _STATE_SPECIFIC_CITATIONS.items()
                if marker in name
            ),
            None,
        )
        if required_state and required_state not in normalised_jurisdiction:
            annotation["citation"] = _null_citation()
            annotation["note"] = (
                annotation["note"]
                + " A state-specific reference was omitted because it does not "
                + "match this agreement's jurisdiction."
            )


def _clean_citation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _null_citation()
    def _str_or_null(v: Any) -> str | None:
        return v.strip() if isinstance(v, str) and v.strip() else None
    return {
        "name":    _str_or_null(raw.get("name")),
        "section": _str_or_null(raw.get("section")),
        "url":     _str_or_null(raw.get("url")),
    }


def _clean_annotations(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("clause_id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        risk = str(row.get("risk") or "amber").lower()
        if risk not in _ALLOWED_RISK:
            risk = "amber"

        # Backwards-compatible: accept the legacy freeform `statute`
        # string too and lift it into the new `citation.name` slot.
        citation = row.get("citation")
        if citation is None and isinstance(row.get("statute"), str):
            citation = {"name": row["statute"], "section": None, "url": None}
        citation = _clean_citation(citation)

        note = str(row.get("note") or "").strip() or "No annotation provided."
        topic_hint = row.get("topic_hint")
        if isinstance(topic_hint, str) and topic_hint.strip().lower() in _ALLOWED_TOPIC_HINTS:
            topic_hint = topic_hint.strip().lower()
        else:
            topic_hint = None

        out.append({
            "clause_id": cid,
            "risk": risk,
            "citation": citation,
            "note": note,
            "topic_hint": topic_hint,
        })
    return out


def _empty_result(error: str, expected_ids: set[str]) -> dict[str, Any]:
    return {
        "annotations": [
            {
                "clause_id": cid,
                "risk": "amber",
                "citation": _null_citation(),
                "note": "Stage 2 analysis failed. Please retry.",
                "topic_hint": None,
            }
            for cid in expected_ids
        ],
        "error": error,
    }
