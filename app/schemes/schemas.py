"""Pydantic schemas for the Schemes Finder API."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Wizard input
# ---------------------------------------------------------------------------

class WorkerProfile(BaseModel):
    """Answers from the 3-question wizard on the client. Every field is
    optional so a worker can get useful matches without answering
    everything — the matcher treats missing as "no filter"."""

    state: Optional[str] = Field(
        default=None,
        description="Slug: karnataka, rajasthan, tamil_nadu, ...",
    )
    occupation: Optional[str] = Field(
        default=None,
        description="delivery | cab | domestic | trades | any",
    )
    age: Optional[int] = Field(default=None, ge=10, le=100)
    gender: Optional[str] = Field(
        default=None,
        description="female | male | other | (omitted for no filter)",
    )
    has_bank_account: Optional[bool] = None
    has_eshram: Optional[bool] = None
    has_daughter_under_10: Optional[bool] = None
    likely_means_tested_eligible: Optional[bool] = Field(
        default=None,
        description=(
            "Rough self-report so means-tested schemes surface. Not a "
            "claim of qualification; the official portal decides."
        ),
    )


# ---------------------------------------------------------------------------
# Documents needed
# ---------------------------------------------------------------------------

class SchemeDoc(BaseModel):
    name: str
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Scheme output
# ---------------------------------------------------------------------------

class SchemeSummary(BaseModel):
    key: str
    name: str
    icon: Optional[str] = None
    state_scope: Optional[str] = None
    sort_order: int


class SchemeMatch(SchemeSummary):
    """A scheme row plus a short 'why it matched' explanation the UI
    surfaces so workers know which of their answers pulled the row in."""

    reasons: list[str] = Field(default_factory=list)


class SchemeDetail(BaseModel):
    key: str
    language: str
    name: str
    description: str
    apply_note: Optional[str] = None
    apply_url: Optional[str] = None
    docs_needed: list[SchemeDoc] = Field(default_factory=list)
    estimated_time: Optional[str] = None
    state_scope: Optional[str] = None
    icon: Optional[str] = None
    language_fallback: bool = False


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------

class SchemesListResponse(BaseModel):
    language: str
    schemes: list[SchemeSummary]


class MatchResponse(BaseModel):
    language: str
    matches: list[SchemeMatch]
    total_candidates: int = Field(
        description="How many active schemes existed before filtering."
    )
