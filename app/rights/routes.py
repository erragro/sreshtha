"""
/api/rights — Rights Guide HTTP surface.

Endpoints (all authenticated, read-only):
  GET  /api/rights/cards                       list active cards for a language
  GET  /api/rights/cards/{topic_key}           full card for a language

Language selection:
  - Client passes ``?language=`` (BCP-47 short code: en, hi, bn, ta,
    te, kn, mr). Defaults to ``en``.
  - If the language has no active cards for a topic, the service falls
    back to English and marks the response with ``language_fallback =
    true``. See ``app/rights/service.py`` for the fallback rules.

Content authoring lives in migrations
(``alembic/versions/009_rights_guide_content.py``); this router does
not accept writes. Editing surface for v2.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import db_session_dep, get_current_active_user
from app.models import User
from app.rights import service as rights_service
from app.rights.schemas import (
    FactCardDetail,
    FactCardListResponse,
    FactCardSummary,
)


router = APIRouter(prefix="/api/rights", tags=["rights"])


# Accepted language codes match the CHECK constraint on ``fact_cards``.
# Enforced here as a Query() Literal so an unknown code fails validation
# rather than hitting the DB.
_SUPPORTED_LANGUAGES = ("en", "hi", "bn", "ta", "te", "kn", "mr")


@router.get("/cards", response_model=FactCardListResponse)
def list_cards(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(db_session_dep)],
    language: str = Query(
        default="en",
        description="BCP-47 short code. Falls back to English when the language is not yet active.",
    ),
) -> FactCardListResponse:
    _guard_language(language)

    cards, actual_language = rights_service.list_active_cards(db, language=language)
    return FactCardListResponse(
        language=actual_language,
        cards=[
            FactCardSummary(
                topic_key=c.topic_key,
                title=c.title,
                icon=c.icon,
                sort_order=c.sort_order,
            )
            for c in cards
        ],
    )


@router.get("/cards/{topic_key}", response_model=FactCardDetail)
def get_card(
    topic_key: str,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(db_session_dep)],
    language: str = Query(default="en"),
) -> FactCardDetail:
    _guard_language(language)

    card, actual_language, fell_back = rights_service.get_card_by_topic(
        db, topic_key=topic_key, language=language,
    )
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active Rights Guide card for topic '{topic_key}'.",
        )

    # action_steps stored as JSONB; may be None or empty list.
    action_steps = card.action_steps or []

    return FactCardDetail(
        topic_key=card.topic_key,
        language=actual_language,
        title=card.title,
        summary=card.summary,
        citation=card.citation,
        action_steps=action_steps,
        icon=card.icon,
        sort_order=card.sort_order,
        language_fallback=fell_back,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _guard_language(language: str) -> None:
    if language not in _SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported language '{language}'. "
                f"Supported: {', '.join(_SUPPORTED_LANGUAGES)}."
            ),
        )
