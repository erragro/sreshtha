"""Read queries + matching logic for Schemes Finder.

The matcher walks each active scheme's ``eligibility_rules`` JSONB
against a :class:`WorkerProfile`. Any rule the profile doesn't answer
is treated as "no filter" so partial profiles still surface useful
candidates.

Rules recognised (all optional in the JSONB):
  occupations         list[str]  — "any" wildcards; otherwise must contain profile.occupation
  states              list[str]  — must contain profile.state
  min_age / max_age   int        — inclusive bounds
  gender              str        — "any" wildcards; otherwise must equal profile.gender
  requires_bank_account   bool   — profile must have one when True
  requires_eshram         bool   — profile must be registered when True
  requires_daughter       bool   — profile.has_daughter_under_10 must be True
  means_tested            bool   — surfaces only if profile.likely_means_tested_eligible is True

Also filters by ``scheme.state_scope`` at the SQL level for a small
perf win before Python matching runs.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Scheme, SchemeTranslation
from app.schemes.schemas import SchemeMatch, WorkerProfile


# ---------------------------------------------------------------------------
# List (unfiltered) + detail
# ---------------------------------------------------------------------------

def list_active_schemes(
    db: Session, *, language: str
) -> tuple[list[tuple[Scheme, SchemeTranslation]], str]:
    """Return every active scheme with its translation in the requested
    language, falling back to English if none of the schemes have that
    language yet.

    Returns ``(rows, actual_language)``.
    """
    rows = _fetch_active(db, language=language)
    if rows:
        return rows, language
    if language != "en":
        return _fetch_active(db, language="en"), "en"
    return [], language


def get_scheme_by_key(
    db: Session, *, key: str, language: str
) -> tuple[Optional[Scheme], Optional[SchemeTranslation], str, bool]:
    scheme = db.scalars(
        select(Scheme).where(Scheme.key == key)
        .where(Scheme.is_active.is_(True))
        .where(Scheme.tenant_id.is_(None))
    ).first()
    if scheme is None:
        return None, None, language, False

    translation = db.scalars(
        select(SchemeTranslation)
        .where(SchemeTranslation.scheme_id == scheme.id)
        .where(SchemeTranslation.language == language)
    ).first()
    fell_back = False
    actual = language
    if translation is None and language != "en":
        translation = db.scalars(
            select(SchemeTranslation)
            .where(SchemeTranslation.scheme_id == scheme.id)
            .where(SchemeTranslation.language == "en")
        ).first()
        fell_back = True
        actual = "en"
    return scheme, translation, actual, fell_back


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def match(
    db: Session, *, profile: WorkerProfile, language: str
) -> tuple[list[SchemeMatch], int, str]:
    """Return matched schemes for a worker profile.

    Reasoning is compiled into short human-readable strings on each
    match so the UI can show "Matched because you told us…". Reasons
    are informational — they never claim eligibility.
    """
    all_rows = _fetch_active(db, language=language)
    fell_back = False
    if not all_rows and language != "en":
        all_rows = _fetch_active(db, language="en")
        fell_back = True
    actual = "en" if fell_back else language

    # Optional state-scope prefilter — anything scoped to a state the
    # worker isn't in gets dropped upfront.
    def _passes_state_scope(scheme: Scheme) -> bool:
        if not scheme.state_scope or scheme.state_scope == "all":
            return True
        if profile.state and profile.state == scheme.state_scope:
            return True
        return False

    matches: list[SchemeMatch] = []
    for scheme, translation in all_rows:
        if not _passes_state_scope(scheme):
            continue
        reasons: list[str] = []
        if not _passes_rules(scheme.eligibility_rules or {}, profile, reasons):
            continue
        matches.append(SchemeMatch(
            key=scheme.key,
            name=translation.name,
            icon=scheme.icon,
            state_scope=scheme.state_scope,
            sort_order=scheme.sort_order,
            reasons=reasons,
        ))

    matches.sort(key=lambda m: (m.sort_order, m.name.lower()))
    return matches, len(all_rows), actual


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _fetch_active(db: Session, *, language: str) -> list[tuple[Scheme, SchemeTranslation]]:
    stmt = (
        select(Scheme, SchemeTranslation)
        .join(SchemeTranslation, SchemeTranslation.scheme_id == Scheme.id)
        .where(Scheme.is_active.is_(True))
        .where(Scheme.tenant_id.is_(None))
        .where(SchemeTranslation.language == language)
        .order_by(Scheme.sort_order.asc(), Scheme.key.asc())
    )
    return list(db.execute(stmt).all())


def _passes_rules(rules: dict, profile: WorkerProfile, reasons: list[str]) -> bool:
    # Occupations. Missing / "any" wildcard accepts everything.
    occs = rules.get("occupations") or []
    if occs and "any" not in occs:
        if not profile.occupation or profile.occupation not in occs:
            return False
        reasons.append(f"Matches your {profile.occupation} work.")

    # States (rare — most schemes use scheme.state_scope for this).
    states = rules.get("states") or []
    if states:
        if not profile.state or profile.state not in states:
            return False
        reasons.append(f"Available in {profile.state.title()}.")

    # Age range.
    if profile.age is not None:
        min_age = rules.get("min_age")
        max_age = rules.get("max_age")
        if min_age is not None and profile.age < min_age:
            return False
        if max_age is not None and profile.age > max_age:
            return False
        if min_age is not None or max_age is not None:
            reasons.append("Your age falls inside the scheme's window.")

    # Gender.
    gender_rule = rules.get("gender")
    if gender_rule and gender_rule != "any":
        if not profile.gender or profile.gender != gender_rule:
            return False
        reasons.append(f"Scheme is for {gender_rule} applicants.")

    # Requirements — if the rule is present as True, the profile must
    # affirm the corresponding capability.
    if rules.get("requires_bank_account") and not profile.has_bank_account:
        return False
    if rules.get("requires_eshram") and not profile.has_eshram:
        return False
    if rules.get("requires_daughter") and not profile.has_daughter_under_10:
        return False

    # Means-tested schemes surface only when the worker's self-report
    # suggests they might qualify. This is intentionally soft — the
    # official portal decides for real.
    if rules.get("means_tested"):
        if not profile.likely_means_tested_eligible:
            return False
        reasons.append("Means-tested — worth checking on the portal.")

    return True
