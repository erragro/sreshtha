"""Stage 3 — Synthesise (English only).

Merges Stage 1 (clauses) + Stage 2 (annotations) into the worker-facing
rendition. For each clause, produces three pieces of English text:
  - explanation  Plain-language rewrite of the clause.
  - implication  What this clause means for the worker in practice.
  - action       Concrete step to take, or null if nothing.

Output is always English. Translation to the worker's target language
happens in a separate pass via Sarvam Mayura (see translate.py) —
Gemini is smartest + fastest reasoning in English, Mayura is the
purpose-built Indic translator. Two providers, two responsibilities.

The viewer joins this Stage 3 output back against Stage 1 (for the
original clause text, kept verbatim in whatever language the contract
was written in) and Stage 2 (for the risk colour + statute) at render
time. When contract.target_language != 'en', the viewer picks the
translated version stored under stages.stage_3.translation.rendered
instead of this raw English rendered array.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text as _sql

from app.contracts.stage3_validator import (
    novel_safe_fallback,
    rule_safe_fallback,
    validate_rendered_clause,
)
from app.db import SessionLocal
from app.l2_agents.llm_provider import get_provider


logger = logging.getLogger(__name__)


_SYSTEM_RENDER_ONLY = """You are producing a worker-friendly rendition of a contract in English.

--- PER-CLAUSE ---

For EACH clause you're given, produce three short pieces of English text:

- explanation  Plain-language rewrite of the clause. 1-2 sentences. Not a
               summary — a rewrite the worker can understand. Do NOT lose
               material meaning. Do NOT introduce new obligations.
- implication  What this clause means for the worker in practice.
               1 sentence. Focus on the worker's rights or exposure.
- action       If the worker should do something about this clause, one
               concrete step in 1 sentence. If nothing needs doing,
               return null.

Enforcement rules:
- If the input clause is 'risk': 'red', the action field MUST NOT be null.
  A red clause without a concrete action is a bug. If genuinely no action
  is possible, action = "Ask the platform in writing to clarify or waive
  this clause and save the response."
- If the input clause carries a topic_hint (mapping to a Rights Guide
  fact card), reference the card in the action or implication: e.g.
  "See Rights Guide → 'Injury on the job' for the escalation ladder."
- If the input carries a citation with a section (e.g. "Section 113 of
  the Code on Social Security 2020"), weave the section reference into
  the implication when it strengthens the worker's position.

Tone rules (strict — Mayura will translate this English text into the
worker's language, so tone preserved here carries through):
- Warm, direct, informational. Register of a helpful older sibling.
- No em dashes (—). Use commas or full stops.
- No corporate register ("kindly", "we regret", "as per").
- No policy language ("as per our terms", "per our guidelines").
- No negative-emotion vocabulary ("frustration", "disappointment", "annoying").
- Max 3 sentences per field.
- Use simple English words. Assume a translator will render each field
  into another language; avoid idioms and puns.

Return ONLY a JSON object with this shape (no prose, no code fences):

{
  "rendered": [
    {
      "clause_id": "<matches an id from the input>",
      "explanation": "<plain-language English rewrite>",
      "implication": "<what this means for the worker, in English>",
      "action": "<one concrete step in English, or null (never null for red clauses)>"
    },
    ...
  ]
}
"""


# System prompt for the second, small, overview-generation call. Runs
# once at the end after all per-clause chunks have completed, so it can
# see the whole rendered contract and pick genuine top priorities
# rather than chunk-local ones.
_SYSTEM_OVERVIEW_ONLY = """You are writing a top-level summary of a contract analysis for a worker.

Input: the whole rendered clause set with risk tiers already assigned.

Produce two outputs:
- top_summary  1-2 sentences. What kind of contract this is and what
               the worker should notice first. Warm tone. No jargon.
               No em dashes.
- top_actions  1 to 3 highest-priority actions from the red-tier
               clauses. Each action is one sentence, concrete, and
               procedural (starts with a verb, points to an authority,
               portal, or documentation step). Draw them from the
               actions already emitted on individual clauses — this is
               a compression, not a new inference.

Tone rules (strict — Mayura will translate this into the worker's
language):
- Warm, direct, informational. Register of a helpful older sibling.
- No em dashes. No corporate register. No negative-emotion vocabulary.
- Simple English words. Avoid idioms and puns.

Return ONLY JSON of this shape (no prose, no code fences):

{
  "top_summary": "<1-2 sentence English summary>",
  "top_actions": [
    "<one procedural action, one sentence>",
    "<another procedural action, if relevant>"
  ]
}
"""


from concurrent.futures import ThreadPoolExecutor, as_completed


# Chunk size + parallelism knobs. Five clauses per chunk keeps each
# call well under Gemini's output ceiling and lets a 30-clause
# contract finish in ~4-5s instead of ~15s sequential. Concurrency of
# 6 respects Vertex's default per-project QPS.
_STAGE3_CHUNK_SIZE = 5
_STAGE3_MAX_WORKERS = 6

_STATE_SPECIFIC_RULE_CITATIONS = {
    "karnataka platform-based gig workers": "karnataka",
    "rajasthan platform based gig workers": "rajasthan",
}


def synthesise(
    stage_1_output: dict[str, Any],
    stage_2_output: dict[str, Any],
) -> dict[str, Any]:
    """Run Stage 3. Always emits English. Returns
    {overview, rendered: [...], error: None}. Translation to the
    worker's chosen target language happens in a subsequent pass via
    translate.translate_stage_3().

    Provider mapping (per-stage hybrid architecture):
      - Classifier: OpenAI ``gpt-4o-mini`` (role="fast") maps every
        clause to a ``clause_rules`` slug or "novel". Single call for
        the whole contract.
      - Generator: Vertex AI Gemini 2.5 Flash. Gemini's warmer tone
        is a better fit for the pre-translation English that Mayura
        hands to workers.
      - Per-clause path:
        * matched     → prompt carries the rule's ``generation_rules``,
                        forbidden/required content, and citation
        * novel       → prompt carries only the universal rules
      - Validator (``stage3_validator``) runs on every emitted clause
        regardless of source. Failed validation triggers one retry
        with corrections; still failing → safe fallback (rule's
        canonical or the universal novel fallback).
      - ``source`` tag on each rendered clause: "library-rule" |
        "novel-llm" | "fallback" — for A/B measurement.

    Batching (Mayura-style):
      - Clauses are chunked into groups of ``_STAGE3_CHUNK_SIZE`` and
        run through Vertex in parallel via a thread pool.
      - The ``overview`` block is generated from the last chunk after
        we've seen the whole contract's per-clause output.
    """
    clauses = stage_1_output.get("clauses") or []
    if not clauses:
        return {
            "overview": {"top_summary": None, "top_actions": []},
            "rendered": [],
            "error": None,
        }

    annotations = {
        a["clause_id"]: a for a in (stage_2_output.get("annotations") or [])
        if isinstance(a, dict) and isinstance(a.get("clause_id"), str)
    }

    contract_type = stage_1_output.get("contract_type") or "unknown"
    metadata = stage_1_output.get("metadata") or {}
    expected_ids = {c["id"] for c in clauses}

    # Step 1: load the active clause_rules library. One DB round trip
    # per Stage 3 run — cached in the caller's DB session if hot.
    with SessionLocal() as db:
        rules_by_slug = _load_active_clause_rules(db)

    # Step 2: classify every clause against the library. One
    # gpt-4o-mini call for the whole contract — cheap and fast.
    classifier = get_provider("en", provider="openai")
    classifications = _classify_clauses(
        classifier=classifier,
        clauses=clauses,
        rules_by_slug=rules_by_slug,
    )

    # Step 3: per-clause rendering + validation, chunked in parallel.
    generator = get_provider("en", provider="vertex")
    chunks: list[list[dict[str, Any]]] = [
        clauses[i : i + _STAGE3_CHUNK_SIZE]
        for i in range(0, len(clauses), _STAGE3_CHUNK_SIZE)
    ]

    rendered_all: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=_STAGE3_MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                _render_chunk,
                provider=generator,
                contract_type=contract_type,
                metadata=metadata,
                clauses_chunk=chunk,
                annotations=annotations,
                classifications=classifications,
                rules_by_slug=rules_by_slug,
            ): idx
            for idx, chunk in enumerate(chunks)
        }
        results_by_idx: dict[int, list[dict[str, Any]]] = {}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                results_by_idx[idx] = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.warning("stage 3 chunk %d failed: %s", idx, exc)
                results_by_idx[idx] = []

    # Reassemble in original clause order.
    for idx in range(len(chunks)):
        rendered_all.extend(results_by_idx.get(idx, []))

    # Overview from the whole rendered set.
    overview = _generate_overview(
        provider=generator,
        contract_type=contract_type,
        metadata=metadata,
        rendered=rendered_all,
        annotations=annotations,
    )

    # Backfill missing clauses.
    seen = {r["clause_id"] for r in rendered_all}
    for cid in expected_ids - seen:
        rendered_all.append({
            "clause_id": cid,
            "explanation": "This clause could not be re-rendered.",
            "implication": "Review the original text.",
            "action": None,
            "source": "fallback",
        })

    # Log source breakdown for A/B measurement.
    source_counts: dict[str, int] = {}
    for r in rendered_all:
        s = r.get("source") or "novel-llm"
        source_counts[s] = source_counts.get(s, 0) + 1
    logger.info("stage 3 source breakdown: %s", source_counts)

    return {"overview": overview, "rendered": rendered_all, "error": None}


# ---------------------------------------------------------------------------
# clause_rules loading + classifier
# ---------------------------------------------------------------------------


def _load_active_clause_rules(db) -> dict[str, dict[str, Any]]:
    """Return a dict of ``{slug: rule_row}`` for every active
    clause_rules row visible to the current tenant (v1: shared library
    only, tenant_id IS NULL)."""
    rows = db.execute(_sql("""
        SELECT slug, name, description, contract_types, default_risk_tier,
               citation, topic_hint, generation_rules,
               forbidden_content, required_content, safe_fallback
          FROM clause_rules
         WHERE is_active = true
           AND tenant_id IS NULL
    """)).mappings().all()
    return {r["slug"]: dict(r) for r in rows}


def _classify_clauses(
    *,
    classifier,
    clauses: list[dict[str, Any]],
    rules_by_slug: dict[str, dict[str, Any]],
) -> dict[str, str | None]:
    """One gpt-4o-mini call classifies every clause against the rule
    library. Returns ``{clause_id: slug_or_None}``."""

    if not clauses or not rules_by_slug:
        return {c["id"]: None for c in clauses}

    taxonomy = [
        {"slug": slug, "name": r["name"], "description": r["description"]}
        for slug, r in rules_by_slug.items()
    ]
    payload = {
        "taxonomy": taxonomy,
        "clauses": [
            {"id": c["id"], "text": c["text"][:800]}  # cap for token budget
            for c in clauses
        ],
    }
    system = (
        "You are a fast classifier mapping contract clauses to a "
        "taxonomy of clause patterns. For each clause, return the slug "
        "of the best-matching pattern from the taxonomy or 'novel' if "
        "no pattern reasonably fits. Match on semantic pattern, not "
        "on individual words. Be conservative — output 'novel' when "
        "the best match is only weakly relevant.\n\n"
        "Return ONLY JSON of shape:\n"
        "{\n"
        '  "classifications": [\n'
        '    {"clause_id": "<id>", "slug": "<taxonomy slug or novel>"},\n'
        "    ...\n"
        "  ]\n"
        "}"
    )
    raw = classifier.chat(
        role="fast",  # gpt-4o-mini
        system=system,
        user=json.dumps(payload, indent=2),
        max_tokens=2000,
        temperature=0.0,
    )
    text = raw.strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("stage 3 classifier: could not parse response")
        return {c["id"]: None for c in clauses}

    out: dict[str, str | None] = {c["id"]: None for c in clauses}
    for row in (parsed.get("classifications") or []):
        if not isinstance(row, dict):
            continue
        cid = row.get("clause_id")
        slug = row.get("slug")
        if not isinstance(cid, str) or cid not in out:
            continue
        if isinstance(slug, str) and slug in rules_by_slug:
            out[cid] = slug
        # anything else → None (novel)
    return out


def _render_chunk(
    *,
    provider,
    contract_type: str,
    metadata: dict[str, Any],
    clauses_chunk: list[dict[str, Any]],
    annotations: dict[str, dict[str, Any]],
    classifications: dict[str, str | None],
    rules_by_slug: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Render one chunk of clauses. Each clause is rendered under
    either its matched rule's constraints (rule-based prompt) or the
    universal fallback prompt (novel). Every emitted clause is
    validated against ``stage3_validator``; failures retry once, then
    fall back to the safe canonical."""

    out: list[dict[str, Any]] = []
    for clause in clauses_chunk:
        cid = clause["id"]
        annotation = annotations.get(cid, {})
        risk = annotation.get("risk", "amber")
        topic_hint = annotation.get("topic_hint")
        rule_slug = classifications.get(cid)
        rule = rules_by_slug.get(rule_slug) if rule_slug else None
        if rule is not None and not _rule_applies_in_jurisdiction(rule, metadata):
            # A matched pattern can still be rendered as a novel clause, but
            # its state-specific rule must not inject another state's law.
            rule = None

        # Attempt 1: rule-based (or novel) generation.
        rendered = _render_one_clause(
            provider=provider,
            contract_type=contract_type,
            metadata=metadata,
            clause=clause,
            annotation=annotation,
            rule=rule,
            correction_hints=None,
        )
        result = validate_rendered_clause(
            rendered, risk=risk, rule=rule, topic_hint=topic_hint,
        )

        if not result.valid:
            # Attempt 2: retry with corrections naming the failed rules.
            logger.info(
                "stage 3 %s: validation failed on attempt 1 for clause %s: %s",
                rule_slug or "novel", cid, "; ".join(result.errors)[:200],
            )
            rendered = _render_one_clause(
                provider=provider,
                contract_type=contract_type,
                metadata=metadata,
                clause=clause,
                annotation=annotation,
                rule=rule,
                correction_hints=result.errors,
            )
            result = validate_rendered_clause(
                rendered, risk=risk, rule=rule, topic_hint=topic_hint,
            )

        if result.valid:
            corrected = result.corrected or rendered
            source = "library-rule" if rule is not None else "novel-llm"
            out.append({
                "clause_id": cid,
                "explanation": corrected.get("explanation", ""),
                "implication": corrected.get("implication", ""),
                "action":      corrected.get("action"),
                "source":      source,
            })
        else:
            # Safe fallback path.
            logger.warning(
                "stage 3 %s: two-strike validation failure on %s; using safe fallback",
                rule_slug or "novel", cid,
            )
            fallback = rule_safe_fallback(rule) or novel_safe_fallback()
            out.append({
                "clause_id": cid,
                "explanation": fallback.get("explanation", ""),
                "implication": fallback.get("implication", ""),
                "action":      fallback.get("action"),
                "source":      "fallback",
            })
    return out


def _render_one_clause(
    *,
    provider,
    contract_type: str,
    metadata: dict[str, Any],
    clause: dict[str, Any],
    annotation: dict[str, Any],
    rule: dict[str, Any] | None,
    correction_hints: list[str] | None,
) -> dict[str, Any]:
    """Single-clause LLM call. Rule-based prompt if rule is not None,
    universal prompt otherwise. Returns the raw rendered dict
    ``{explanation, implication, action}`` (not yet validated)."""

    system = _SYSTEM_RENDER_ONLY
    if rule is not None:
        system = system + "\n\n" + _rule_addendum(rule)

    input_payload = {
        "contract_type": contract_type,
        "metadata": metadata,
        "clause": {
            "id": clause["id"],
            "heading": clause.get("heading"),
            "text": clause["text"],
            "risk":       annotation.get("risk", "amber"),
            "citation":   annotation.get("citation"),
            "note":       annotation.get("note"),
            "topic_hint": annotation.get("topic_hint"),
        },
    }
    user = (
        "Render THIS clause following the rules above.\n"
        + json.dumps(input_payload, ensure_ascii=False, indent=2)
    )
    if correction_hints:
        user = (
            user
            + "\n\nYour previous response was rejected. Fix these issues:\n"
            + "\n".join(f"- {h}" for h in correction_hints)
        )

    raw = provider.chat(
        role="smart",  # gemini-2.5-flash
        system=system,
        user=user,
        max_tokens=1500,
        temperature=0.2,
    )
    text = raw.strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("stage 3 single-clause parse failed for %s", clause.get("id"))
        return {"explanation": "", "implication": "", "action": None}

    # Some prompts return {"rendered": [{...}]} shape; unwrap if so.
    if isinstance(data, dict) and "rendered" in data and isinstance(data["rendered"], list):
        if data["rendered"]:
            data = data["rendered"][0]
        else:
            data = {}
    if not isinstance(data, dict):
        return {"explanation": "", "implication": "", "action": None}

    return {
        "explanation": _clean_field(data.get("explanation"), fallback=""),
        "implication": _clean_field(data.get("implication"), fallback=""),
        "action":      _normalise_action(data.get("action")),
    }


def _rule_applies_in_jurisdiction(rule: dict[str, Any], metadata: dict[str, Any]) -> bool:
    """Whether a rule with a state-law citation can be used for this contract.

    The classifier recognises clause patterns, not legal applicability. Rules
    carrying central-law citations remain available everywhere; rules carrying
    Karnataka or Rajasthan references require that exact jurisdiction.
    """
    citation = rule.get("citation") or {}
    citation_name = str(citation.get("name") or "").lower()
    required_state = next(
        (
            state
            for marker, state in _STATE_SPECIFIC_RULE_CITATIONS.items()
            if marker in citation_name
        ),
        None,
    )
    if required_state is None:
        return True
    jurisdiction = str(metadata.get("jurisdiction") or "").lower()
    return required_state in jurisdiction


def _rule_addendum(rule: dict[str, Any]) -> str:
    """Assemble a per-clause rule-spec block that gets appended to the
    system prompt when a rule matches."""
    parts = [
        "--- CLAUSE-SPECIFIC RULE ---",
        f"Pattern name: {rule.get('name', '')}",
        f"Description:  {rule.get('description', '')}",
        f"Default risk: {rule.get('default_risk_tier', 'amber')}",
        "",
        "Generation rules for this pattern:",
        (rule.get("generation_rules") or "").strip(),
    ]
    citation = rule.get("citation") or {}
    if citation.get("name") or citation.get("section"):
        parts.append("")
        parts.append(
            "Verified citation to include when writing the implication: "
            + (citation.get("name") or "")
            + (f", {citation['section']}" if citation.get("section") else "")
        )
        if citation.get("url"):
            parts.append("URL: " + citation["url"])

    forbidden = rule.get("forbidden_content") or []
    if forbidden:
        parts.append("")
        parts.append(
            "Do NOT use any of these phrases (any casing): "
            + ", ".join(f"'{f}'" for f in forbidden)
        )

    required = rule.get("required_content") or []
    if required:
        parts.append("")
        parts.append(
            "The output MUST contain at least one of these anchors: "
            + ", ".join(f"'{r}'" for r in required)
        )

    parts.append("")
    parts.append(
        "Return ONLY a JSON object of shape: "
        "{\"explanation\": \"...\", \"implication\": \"...\", "
        "\"action\": \"... or null\"}"
    )
    return "\n".join(parts)


def _normalise_action(value: Any) -> str | None:
    """Clean the action field to null-or-string, handling the "null"
    string case Gemini sometimes emits."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or v.lower() in {"null", "none", "n/a", "na", "-"}:
        return None
    return v.replace("—", ",")


def _generate_overview(
    *,
    provider,
    contract_type: str,
    metadata: dict[str, Any],
    rendered: list[dict[str, Any]],
    annotations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """One extra Gemini call to synthesise the overview block from the
    full rendered clause set. Small payload (just clause_id + risk +
    the LLM-rendered explanation), fast response."""

    if not rendered:
        return {"top_summary": None, "top_actions": []}

    # Compact input: give the LLM only what it needs to write a summary
    # and pick the top actions.
    summary_payload = {
        "contract_type": contract_type,
        "metadata": metadata,
        "clauses": [
            {
                "id": r["clause_id"],
                "risk": annotations.get(r["clause_id"], {}).get("risk", "amber"),
                "explanation": r.get("explanation", ""),
                "action": r.get("action"),
            }
            for r in rendered
        ],
    }

    raw = provider.chat(
        role="smart",
        system=_SYSTEM_OVERVIEW_ONLY,
        user=(
            "Produce the top-level overview from the rendered clauses. "
            "Return JSON only.\n"
            + json.dumps(summary_payload, ensure_ascii=False, indent=2)
        ),
        max_tokens=800,
        temperature=0.2,
    )
    try:
        text = raw.strip()
        m = _CODE_FENCE_RE.search(text)
        if m:
            text = m.group(1).strip()
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("stage 3 overview: could not parse response")
        return {"top_summary": None, "top_actions": []}
    return _clean_overview(data)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


_RED_FALLBACK_ACTION = (
    "Ask the platform in writing to clarify or waive this clause and "
    "save the response."
)


def _parse(
    raw: str,
    *,
    expected_ids: set[str],
    red_ids: set[str] | None = None,
) -> dict[str, Any]:
    red_ids = red_ids or set()

    if not raw or not raw.strip():
        return _empty_result("empty response from stage 3 llm", expected_ids)

    text = raw.strip()
    m = _CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("stage 3: could not parse response; raw=%r", text[:300])
        return _empty_result("could not parse stage 3 response as JSON", expected_ids)

    if not isinstance(data, dict):
        return _empty_result("stage 3 response was not an object", expected_ids)

    rendered = _clean_rendered(data.get("rendered") or [])
    overview = _clean_overview(data.get("overview"))

    # Backfill missing clauses so the viewer always has something to show.
    seen = {r["clause_id"] for r in rendered}
    for cid in expected_ids - seen:
        rendered.append({
            "clause_id": cid,
            "explanation": "This clause could not be re-rendered.",
            "implication": "Review the original text.",
            "action": None,
        })

    # Enforcement: every red-tier clause must carry a concrete action.
    # If the LLM elided it, fill with a safe default. Logged separately
    # so we can measure how often this triggers.
    filled = 0
    for r in rendered:
        if r["clause_id"] in red_ids and not r.get("action"):
            r["action"] = _RED_FALLBACK_ACTION
            filled += 1
    if filled:
        logger.info(
            "stage 3: filled fallback action on %d red-tier clauses "
            "(LLM under-emitted)",
            filled,
        )

    return {"overview": overview, "rendered": rendered, "error": None}


def _clean_overview(raw: Any) -> dict[str, Any]:
    """Normalise the top-level overview block. Missing / malformed → an
    empty overview so the viewer can render nothing at all."""
    if not isinstance(raw, dict):
        return {"top_summary": None, "top_actions": []}

    top_summary = raw.get("top_summary")
    top_summary = (
        top_summary.strip()
        if isinstance(top_summary, str) and top_summary.strip()
        else None
    )

    actions_raw = raw.get("top_actions") or []
    actions: list[str] = []
    if isinstance(actions_raw, list):
        for a in actions_raw:
            if isinstance(a, str) and a.strip():
                actions.append(a.strip())
    return {"top_summary": top_summary, "top_actions": actions[:3]}  # cap at 3


def _clean_rendered(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cid = row.get("clause_id")
        if not isinstance(cid, str) or not cid.strip():
            continue
        explanation = _clean_field(row.get("explanation"), fallback="")
        implication = _clean_field(row.get("implication"), fallback="")
        action_raw = row.get("action")
        # Explicit null OR empty string → no action. Also catch the
        # literal strings "null" / "none" / "n/a" because Gemini
        # sometimes returns those despite the instruction; rendering
        # them verbatim would put "Suggested action: null" in the UI.
        if action_raw is None:
            action = None
        else:
            action_str = _clean_field(action_raw, fallback="")
            if action_str.lower() in {"null", "none", "n/a", "na", "-"}:
                action = None
            else:
                action = action_str or None
        out.append({
            "clause_id": cid,
            "explanation": explanation,
            "implication": implication,
            "action": action,
        })
    return out


def _clean_field(value: Any, *, fallback: str) -> str:
    """Strip em dashes as a defence in depth against the LLM slipping
    them into user-facing copy. Tone spec section 8.4 bans them."""
    if not isinstance(value, str):
        return fallback
    return value.strip().replace("—", ",")


def _empty_result(error: str, expected_ids: set[str]) -> dict[str, Any]:
    return {
        "overview": {"top_summary": None, "top_actions": []},
        "rendered": [
            {
                "clause_id": cid,
                "explanation": "Rendering failed. Please retry.",
                "implication": "",
                "action": None,
            }
            for cid in expected_ids
        ],
        "error": error,
    }
