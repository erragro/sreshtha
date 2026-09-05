"""Pydantic schemas for the Rights Guide API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Action step shape
# ---------------------------------------------------------------------------

class ActionStep(BaseModel):
    """One row in a card's `What to do about it` list. Deliberately
    minimal: label + description + optional url. The frontend renders
    the url as a link only if present."""

    label: str
    description: str
    url: Optional[str] = None


# ---------------------------------------------------------------------------
# Fact card responses
# ---------------------------------------------------------------------------

class FactCardSummary(BaseModel):
    """Compact card row for the list view."""

    topic_key: str = Field(description="Stable slug used as the URL parameter.")
    title: str
    icon: Optional[str] = None
    sort_order: int


class FactCardDetail(BaseModel):
    """Full card for the detail view. Same fields the migration seeds."""

    topic_key: str
    language: str = Field(description="BCP-47 language subtag of the returned copy.")
    title: str
    summary: str = Field(
        description="2 to 3 short paragraphs. Newline-separated. Rendered as plain text."
    )
    citation: Optional[str] = None
    action_steps: list[ActionStep] = Field(default_factory=list)
    icon: Optional[str] = None
    sort_order: int
    language_fallback: bool = Field(
        default=False,
        description=(
            "True when the requested language did not have an active card "
            "and the response fell back to English."
        ),
    )


class FactCardListResponse(BaseModel):
    """List envelope so we can add pagination/faceting later without a
    breaking-change to callers."""

    language: str
    cards: list[FactCardSummary]
