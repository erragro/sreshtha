"""Stage 1 — Understand.

Reads the OCR'd text of a contract and extracts a structured list of
clauses plus a contract-type classification. No legal reasoning happens
here (Stage 2 does that); this stage just imposes a schema on prose so
the downstream annotator has predictable shapes to work with.

The `clauses` array is what the viewer renders directly — each clause
becomes a row in the clause-by-clause UI, and its id is what the "ask
about this clause" chatbot hook references. Ids are stable strings so
they survive re-processing (rerunning Stage 1 on the same OCR text
produces the same ids).

Contract type is a fixed enum: aggregator | labour | vendor | rental |
unknown. Aggregator is the most common (Swiggy / Uber / Ola / Rapido);
labour covers direct-employment contracts; vendor covers B2B supply
agreements a gig-adjacent business might sign; rental covers vehicle
leases (common for delivery riders); unknown when the classifier can't
decide with confidence.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.l2_agents.llm_provider import get_provider


logger = logging.getLogger(__name__)


_ALLOWED_TYPES = {"aggregator", "labour", "vendor", "rental", "unknown"}


_SYSTEM = """You are analysing a contract or agreement between a worker and a company/platform.

Your job is to:

1. Extract each clause as a separate entry. A clause is a numbered section,
   a titled paragraph, or any standalone provision. Preserve the original
   language — do NOT translate the clause text.

2. Classify the contract as one of:
   - aggregator  (worker signs onto a platform: Swiggy, Uber, Ola, Rapido, Urban Company, etc.)
   - labour      (direct employment contract with a named employer)
   - vendor      (business-to-business supply agreement)
   - rental      (vehicle or equipment lease agreement)
   - unknown     (cannot determine with confidence)

3. Extract document-level metadata (parties, dates, jurisdiction). This
   gives the downstream stages the context they need to reason correctly
   (a Karnataka jurisdiction unlocks welfare-board reasoning; a signature
   date affects which statute revision applies).

Return ONLY a JSON object with this shape (no prose):

{
  "contract_type": "<one of the five above>",
  "confidence": <float 0.0 to 1.0>,
  "metadata": {
    "parties": [
      {"role": "worker" | "platform" | "employer" | "vendor" | "lessor" | "lessee" | "other",
       "name": "<name as written, or null>"}
    ],
    "signature_date": "<ISO date YYYY-MM-DD, or null if unclear>",
    "effective_date": "<ISO date YYYY-MM-DD, or null if unclear>",
    "term": "<free text: '12 months', 'indefinite', 'until terminated', or null>",
    "jurisdiction": "<state or 'India', or null>",
    "governing_language": "<language of the contract text: en, hi, bn, ta, te, kn, mr, or 'mixed'>"
  },
  "clauses": [
    {
      "id": "<stable string, e.g. clause_1 or clause_3a>",
      "heading": "<the clause heading or null if there isn't one>",
      "section_number": "<the section number as written, or null>",
      "text": "<the verbatim clause text in the original language>"
    },
    ...
  ]
}

Guidelines:
- If the document has explicit numbered clauses (1., 2.1, 3(a)), use those numbers in section_number and derive id from them.
- If there are no explicit numbers, invent stable ids: clause_1, clause_2, ...
- Preserve line breaks within a clause using \\n.
- Metadata: use null for anything you cannot infer with reasonable confidence. Do NOT hallucinate parties or dates. If the contract is mostly one language with occasional English loanwords, governing_language is the majority language, not 'mixed'.
- If the OCR text is garbled or clearly not a contract, return contract_type='unknown', confidence=0, clauses=[], metadata with all null fields.
- Do NOT summarise or reword clauses. Verbatim only.
"""


def analyse(ocr_text: str, language: str = "en") -> dict[str, Any]:
    """Run Stage 1 on the OCR text. Returns the parsed dict; the caller
    persists it into the row's `stages.stage_1` slot.

    Provider mapping (per-stage hybrid architecture):
      - Primary: OpenAI ``gpt-4o-mini`` with Structured Outputs. Cheap,
        fast, schema-guaranteed JSON — extraction is a shape-imposition
        task where mini is at parity with 4o.
      - Fallback: OpenAI ``gpt-4o`` (smart role). Triggered when mini
        emits confidence < 0.4 or zero clauses. Costs ~15× more per
        call but ships only on pathological documents.
    """
    provider = get_provider(language, provider="openai")

    raw = provider.chat(
        role="fast",  # gpt-4o-mini
        system=_SYSTEM,
        user=f"OCR text of the contract:\n\n{ocr_text}",
        # 4o-mini output ceiling is 16K. Real 3-8 page contracts fit
        # comfortably inside this budget; if we ever see truncation we
        # fall through to the smart-role fallback below.
        max_tokens=16000,
        temperature=0.0,
        schema=_STAGE1_SCHEMA,
    )
    result = _parse(raw)

    # Fallback path: confidence gate. Extraction that comes back with
    # low confidence OR zero clauses gets one retry on gpt-4o (smart).
    if _needs_fallback(result):
        logger.info(
            "stage 1: mini output low-confidence (%.2f, %d clauses) — "
            "retrying on smart model",
            result.get("confidence", 0.0),
            len(result.get("clauses") or []),
        )
        raw = provider.chat(
            role="smart",  # gpt-4o
            system=_SYSTEM,
            user=f"OCR text of the contract:\n\n{ocr_text}",
            max_tokens=16000,
            temperature=0.0,
            schema=_STAGE1_SCHEMA,
        )
        result = _parse(raw)
        result["_fallback"] = "smart"

    return result


def _needs_fallback(result: dict[str, Any]) -> bool:
    if result.get("error"):
        return True
    conf = float(result.get("confidence") or 0.0)
    clauses = result.get("clauses") or []
    return conf < 0.4 or len(clauses) == 0


# ---------------------------------------------------------------------------
# Structured Outputs schema
# ---------------------------------------------------------------------------
#
# Mirrors the shape the system prompt commits to. OpenAI Structured
# Outputs enforces this exactly; Vertex Gemini honours it if a caller
# routes here through the vertex path. Kept as a plain dict so it works
# with both providers unchanged.

_STAGE1_SCHEMA: dict[str, Any] = {
    "name": "contract_extraction",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["contract_type", "confidence", "metadata", "clauses"],
        "properties": {
            "contract_type": {
                "type": "string",
                "enum": list(sorted(_ALLOWED_TYPES)),
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "metadata": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "parties", "signature_date", "effective_date",
                    "term", "jurisdiction", "governing_language",
                ],
                "properties": {
                    "parties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["role", "name"],
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["worker", "platform", "employer",
                                             "vendor", "lessor", "lessee", "other"],
                                },
                                "name": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "signature_date":     {"type": ["string", "null"]},
                    "effective_date":     {"type": ["string", "null"]},
                    "term":               {"type": ["string", "null"]},
                    "jurisdiction":       {"type": ["string", "null"]},
                    "governing_language": {
                        "type": ["string", "null"],
                        "enum": ["en", "hi", "bn", "ta", "te", "kn", "mr", "mixed", None],
                    },
                },
            },
            "clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "heading", "section_number", "text"],
                    "properties": {
                        "id":             {"type": "string"},
                        "heading":        {"type": ["string", "null"]},
                        "section_number": {"type": ["string", "null"]},
                        "text":           {"type": "string"},
                    },
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def _parse(raw: str) -> dict[str, Any]:
    if not raw or not raw.strip():
        return _empty_result("empty response from stage 1 llm")

    text = raw.strip()
    # Strip code fences if Gemini added them despite the instruction.
    m = _CODE_FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Log both the head and the tail — a truncated response looks
        # fine at the head but breaks at the tail, and vice versa.
        logger.warning(
            "stage 1: could not parse response as JSON (%s); "
            "raw len=%d, head=%r, tail=%r",
            exc, len(text), text[:200], text[-200:],
        )
        # Salvage attempt: some responses truncate mid-clause. Look for
        # the last complete clause boundary and try to reconstruct.
        recovered = _try_recover_truncated(text)
        if recovered:
            logger.info("stage 1: recovered %d clauses from truncated response", len(recovered.get("clauses") or []))
            return _finalize(recovered)
        return _empty_result(
            f"could not parse Gemini's response as JSON. It may have run "
            f"past the output limit (response was {len(text)} characters)."
        )

    if not isinstance(data, dict):
        return _empty_result("stage 1 response was not an object")

    return _finalize(data)


def _finalize(data: dict) -> dict[str, Any]:
    contract_type = str(data.get("contract_type") or "unknown").lower()
    if contract_type not in _ALLOWED_TYPES:
        contract_type = "unknown"

    try:
        confidence = float(data.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    clauses_raw = data.get("clauses") or []
    clauses = _clean_clauses(clauses_raw)

    metadata = _clean_metadata(data.get("metadata"))

    return {
        "contract_type": contract_type,
        "confidence": confidence,
        "metadata": metadata,
        "clauses": clauses,
        "error": None,
    }


_ROLE_ALLOWED = {"worker", "platform", "employer", "vendor", "lessor", "lessee", "other"}
_LANG_ALLOWED = {"en", "hi", "bn", "ta", "te", "kn", "mr", "mixed"}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_metadata(raw: Any) -> dict[str, Any]:
    """Normalise the metadata block. Missing / malformed → all-null
    metadata, never a raise. Every caller can treat the shape as
    guaranteed."""

    def _null_metadata() -> dict[str, Any]:
        return {
            "parties": [],
            "signature_date": None,
            "effective_date": None,
            "term": None,
            "jurisdiction": None,
            "governing_language": None,
        }

    if not isinstance(raw, dict):
        return _null_metadata()

    parties_raw = raw.get("parties")
    parties: list[dict[str, Any]] = []
    if isinstance(parties_raw, list):
        for p in parties_raw:
            if not isinstance(p, dict):
                continue
            role = str(p.get("role") or "").strip().lower()
            if role not in _ROLE_ALLOWED:
                role = "other"
            name = p.get("name")
            name = str(name).strip() if isinstance(name, str) and name.strip() else None
            parties.append({"role": role, "name": name})

    def _iso_or_null(v: Any) -> str | None:
        if isinstance(v, str) and _ISO_DATE.match(v.strip()):
            return v.strip()
        return None

    lang = raw.get("governing_language")
    if isinstance(lang, str):
        lang = lang.strip().lower()
        if lang not in _LANG_ALLOWED:
            lang = None
    else:
        lang = None

    jur = raw.get("jurisdiction")
    jur = str(jur).strip() if isinstance(jur, str) and jur.strip() else None

    term = raw.get("term")
    term = str(term).strip() if isinstance(term, str) and term.strip() else None

    return {
        "parties": parties,
        "signature_date": _iso_or_null(raw.get("signature_date")),
        "effective_date": _iso_or_null(raw.get("effective_date")),
        "term": term,
        "jurisdiction": jur,
        "governing_language": lang,
    }


def _try_recover_truncated(text: str) -> dict[str, Any] | None:
    """Salvage a truncated Stage 1 response. Gemini's structured output
    typically dies mid-clause when it runs out of tokens: opening braces
    are complete but the last clause is half-written and the closing
    array + object braces are missing. Walk backwards to the last
    complete '}' inside the clauses array, then reassemble.
    """
    # Locate the start of the clauses array.
    array_start = text.find('"clauses"')
    if array_start < 0:
        return None
    bracket_start = text.find("[", array_start)
    if bracket_start < 0:
        return None

    # Find the last complete top-level '}' inside the array by depth-tracking.
    depth = 0
    last_complete_end = -1
    i = bracket_start + 1
    in_string = False
    escaped = False
    while i < len(text):
        c = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    last_complete_end = i
        i += 1

    if last_complete_end < 0:
        return None

    # Reconstruct: everything up to the last complete '}', then close
    # the array + the outer object. contract_type + confidence come
    # from before the clauses array — parse the head separately.
    salvaged = text[:last_complete_end + 1] + "]}"
    try:
        return json.loads(salvaged)
    except json.JSONDecodeError:
        return None


def _clean_clauses(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        cid = str(row.get("id") or f"clause_{i}")
        heading = row.get("heading")
        heading = str(heading).strip() if isinstance(heading, str) and heading.strip() else None
        section_number = row.get("section_number")
        section_number = (
            str(section_number).strip()
            if isinstance(section_number, str) and section_number.strip()
            else None
        )
        out.append({
            "id": cid,
            "heading": heading,
            "section_number": section_number,
            "text": text.strip(),
        })
    return out


def _empty_result(error: str) -> dict[str, Any]:
    return {
        "contract_type": "unknown",
        "confidence": 0.0,
        "metadata": _clean_metadata(None),
        "clauses": [],
        "error": error,
    }
