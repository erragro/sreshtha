"""Deterministic response validator for Stage 3 output.

Runs on every clause's rendered ``{explanation, implication, action}``
tuple regardless of whether the source is a matched rule row or a
novel LLM call. If a rule row is passed in, its ``forbidden_content``,
``required_content``, and ``safe_fallback`` are consulted in addition
to the universal rules.

Design (see PRD §7.4):

- **Universal rules** apply to every rendered clause:
  - tone lint (em dashes → commas, negative-emotion blocklist, corporate-
    register blocklist, "policy language" blocklist)
  - red-tier clauses must have a non-null ``action`` starting with a verb
  - length caps: explanation ≤ 240 chars, implication ≤ 160, action ≤ 200
  - no legal-conclusion verbs ("illegal", "void", "you should sue", etc.)

- **Per-rule rules** apply when a rule row is passed:
  - ``forbidden_content`` substrings must not appear
  - ``required_content`` — at least one substring must appear

- **Escalation injection** — if the clause topic_hint is safety-critical
  (injury, harassment) OR the ``forbidden_content`` matched
  ("harassment", "wage theft"), the India Labourline (1800-419-1550)
  contact is appended to the action field.

The validator returns a ``ValidationResult`` describing which rules
tripped. Caller decides whether to retry with corrections or fall
back to the rule's canonical safe default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Universal rule constants
# ---------------------------------------------------------------------------

_UNIVERSAL_FORBIDDEN = (
    # legal-conclusion verbs — the deterministic sanitiser (§6.2, §7.4)
    "illegal",
    "you should sue",
    "grounds for a lawsuit",
    "is void",
    "is unenforceable",
    # over-reach / advice
    "you are entitled to",
    "you have grounds for",
    # negative emotion — tone lint (§8.4)
    "frustration",
    "annoying",
    "disappointment",
    # corporate register
    "kindly",
    "we regret",
    "as per our",
)

_LENGTH_CAPS = {
    "explanation": 500,   # 240 was too tight for the compound English required by these clauses; 500 gives room without letting it sprawl
    "implication": 400,
    "action":      400,
}

_TERMINAL_PUNCT = re.compile(r"([.!?])")

_LABOURLINE_APPEND = (
    " If in doubt, call India Labourline: 1800-419-1550."
)

_SAFETY_CRITICAL_TOPIC_HINTS = {
    "injury_on_the_job",
    "grievance_escalation",   # harassment escalations share this hint
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # The corrected output after auto-fixes (em-dash rewrite, length
    # trim, escalation injection). Original is never mutated.
    corrected: dict[str, Any] | None = None


def validate_rendered_clause(
    rendered: dict[str, Any],
    *,
    risk: str,
    rule: dict[str, Any] | None = None,
    topic_hint: str | None = None,
) -> ValidationResult:
    """Validate one rendered clause. Returns a ``ValidationResult``
    with a corrected output when auto-fixes apply.

    ``rendered`` — dict with ``explanation``, ``implication``, ``action``.
    ``risk``     — "red" / "amber" / "green" (from Stage 2).
    ``rule``     — the ``clause_rules`` row (dict) if matched; else None.
    ``topic_hint`` — the Rights Guide topic slug for escalation-injection routing.
    """
    errors: list[str] = []
    warnings: list[str] = []
    corrected = dict(rendered)  # shallow copy — we'll patch fields

    # --- Step 1: normalise em dashes (auto-fix, always applied) ---
    for field_ in ("explanation", "implication", "action"):
        value = corrected.get(field_)
        if isinstance(value, str) and "—" in value:
            corrected[field_] = value.replace("—", ",")

    # --- Step 2: universal forbidden-phrase blocklist ---
    for field_ in ("explanation", "implication", "action"):
        value = corrected.get(field_)
        if not isinstance(value, str):
            continue
        low = value.lower()
        for bad in _UNIVERSAL_FORBIDDEN:
            if bad in low:
                errors.append(f"{field_}: contains forbidden phrase '{bad}'")

    # --- Step 3: per-rule forbidden_content ---
    if rule:
        for bad in rule.get("forbidden_content") or []:
            if not isinstance(bad, str) or not bad:
                continue
            low_bad = bad.lower()
            for field_ in ("explanation", "implication", "action"):
                value = corrected.get(field_)
                if isinstance(value, str) and low_bad in value.lower():
                    errors.append(
                        f"{field_}: contains rule-forbidden phrase '{bad}'"
                    )

    # --- Step 4: per-rule required_content ---
    if rule:
        req = rule.get("required_content") or []
        if req:
            # OR semantics: at least one of the anchor phrases must
            # appear across the three fields combined.
            combined = " ".join(
                str(corrected.get(f, "")) for f in ("explanation", "implication", "action")
            ).lower()
            hit = any(str(anchor).lower() in combined for anchor in req if anchor)
            if not hit:
                errors.append(
                    "output does not contain any of the rule's required anchors: "
                    + ", ".join(f"'{a}'" for a in req)
                )

    # --- Step 5: red-tier action requirement ---
    if risk == "red":
        action = corrected.get("action")
        if not isinstance(action, str) or not action.strip():
            errors.append("red-tier clause must have a non-null action")
        else:
            first = action.strip().split()
            if first and not re.match(r"^[A-Z][a-z]+", first[0]):
                warnings.append(
                    f"action does not start with a capitalised verb: {first[0]!r}"
                )

    # --- Step 6: length caps (auto-trim on overflow) ---
    for field_, cap in _LENGTH_CAPS.items():
        value = corrected.get(field_)
        if isinstance(value, str) and len(value) > cap:
            trimmed = _trim_to_sentence(value, cap)
            corrected[field_] = trimmed
            warnings.append(
                f"{field_} exceeded {cap} chars ({len(value)}); trimmed to {len(trimmed)}"
            )

    # --- Step 7: escalation injection for safety-critical topics ---
    if _needs_escalation(topic_hint, rule) and risk in ("red", "amber"):
        action = corrected.get("action")
        if isinstance(action, str) and "1800-419-1550" not in action:
            corrected["action"] = action.rstrip(".! ") + "." + _LABOURLINE_APPEND

    valid = not errors
    return ValidationResult(
        valid=valid, errors=errors, warnings=warnings, corrected=corrected,
    )


# ---------------------------------------------------------------------------
# Fallback derivation
# ---------------------------------------------------------------------------

def rule_safe_fallback(rule: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the rule row's ``safe_fallback`` field as a rendered
    tuple, or None if the rule has none (or no rule was passed)."""
    if not rule:
        return None
    fb = rule.get("safe_fallback") or {}
    if not fb.get("explanation"):
        return None
    return {
        "explanation": fb.get("explanation") or "",
        "implication": fb.get("implication") or "",
        "action":      fb.get("action"),  # may legitimately be null on green fallbacks
    }


def novel_safe_fallback() -> dict[str, Any]:
    """The universal fallback used when a novel clause fails validation
    twice and there is no rule-specific safe default to draw from."""
    return {
        "explanation": "This clause needs manual review.",
        "implication": "The plain-language rewrite could not be produced safely.",
        "action": "Call India Labourline at 1800-419-1550 for help understanding this clause.",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _needs_escalation(topic_hint: str | None, rule: dict[str, Any] | None) -> bool:
    if topic_hint and topic_hint in _SAFETY_CRITICAL_TOPIC_HINTS:
        return True
    if rule and rule.get("topic_hint") in _SAFETY_CRITICAL_TOPIC_HINTS:
        return True
    return False


def _trim_to_sentence(text: str, cap: int) -> str:
    """Trim text to fit under ``cap`` chars at the nearest sentence
    boundary before the cap. Falls back to a hard truncate + ellipsis
    if no boundary is close enough."""
    if len(text) <= cap:
        return text
    # Find sentence-terminal punctuation at or before cap.
    window = text[:cap]
    matches = list(_TERMINAL_PUNCT.finditer(window))
    if matches:
        end = matches[-1].end()
        # Preserve trailing space cleanly.
        return window[:end].rstrip()
    # Hard truncate + word-boundary respect.
    hard = text[:cap - 1].rsplit(" ", 1)[0]
    return hard.rstrip() + "…"
