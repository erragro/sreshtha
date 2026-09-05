"""Read queries for Rights Guide fact cards.

Kept intentionally small: two functions, one for the list view and one
for the detail view. Both enforce the two delivery-side rules:

- Only ``is_active = true`` rows.
- Language fallback: if the requested language has no active card for a
  topic, return the English canonical row and mark ``language_fallback
  = true`` in the response. Never return an inactive card silently.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FactCard


# ---------------------------------------------------------------------------
# Public queries
# ---------------------------------------------------------------------------

def list_active_cards(db: Session, *, language: str) -> tuple[list[FactCard], str]:
    """Return every active card for the requested language, sorted for
    the list view.

    If the language has no active cards at all (e.g. no Bengali cards
    are past native-speaker review yet), fall back to English so the
    Rights Guide list is never empty for an authenticated worker.

    Returns ``(cards, actual_language)`` — the caller can compare
    ``actual_language`` to what was asked for and surface a "translation
    in review" note in the UI when they differ.
    """
    cards = _fetch_active_cards(db, language)
    if cards:
        return cards, language

    if language != "en":
        english = _fetch_active_cards(db, "en")
        return english, "en"

    return [], language


def get_card_by_topic(
    db: Session, *, topic_key: str, language: str
) -> tuple[Optional[FactCard], str, bool]:
    """Return one card for the requested (topic_key, language), or fall
    back to English if the requested language is not yet active for
    this topic.

    Returns ``(card, actual_language, fell_back)``. Card is None if
    the topic itself has no active row in any language.
    """
    card = _fetch_active_card(db, topic_key=topic_key, language=language)
    if card is not None:
        return card, language, False

    if language != "en":
        english = _fetch_active_card(db, topic_key=topic_key, language="en")
        if english is not None:
            return english, "en", True

    return None, language, False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_active_cards(db: Session, language: str) -> list[FactCard]:
    stmt = (
        select(FactCard)
        .where(FactCard.language == language)
        .where(FactCard.is_active.is_(True))
        .where(FactCard.tenant_id.is_(None))  # v1: shared tenant only
        .order_by(FactCard.sort_order.asc(), FactCard.topic_key.asc())
    )
    return list(db.scalars(stmt).all())


def _fetch_active_card(
    db: Session, *, topic_key: str, language: str
) -> Optional[FactCard]:
    stmt = (
        select(FactCard)
        .where(FactCard.topic_key == topic_key)
        .where(FactCard.language == language)
        .where(FactCard.is_active.is_(True))
        .where(FactCard.tenant_id.is_(None))
    )
    return db.scalars(stmt).first()
