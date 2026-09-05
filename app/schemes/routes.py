"""
/api/schemes — Schemes Finder HTTP surface.

Endpoints (authenticated, read-only):
  GET   /api/schemes                       list all active schemes
  GET   /api/schemes/{key}                 detail for one scheme
  POST  /api/schemes/match                 match schemes against a worker profile

Language selection mirrors ``/api/rights``: ``?language=`` param,
fallback to English when the translation is missing.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import db_session_dep, get_current_active_user
from app.models import User
from app.schemes import service as schemes_service
from app.schemes.schemas import (
    MatchResponse,
    SchemeDetail,
    SchemeDoc,
    SchemeSummary,
    SchemesListResponse,
    WorkerProfile,
)


router = APIRouter(prefix="/api/schemes", tags=["schemes"])


_SUPPORTED_LANGUAGES = ("en", "hi", "bn", "ta", "te", "kn", "mr")


def _guard_language(language: str) -> None:
    if language not in _SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language '{language}'. "
                   f"Supported: {', '.join(_SUPPORTED_LANGUAGES)}.",
        )


@router.get("", response_model=SchemesListResponse)
def list_schemes(
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(db_session_dep)],
    language: str = Query(default="en"),
) -> SchemesListResponse:
    _guard_language(language)
    rows, actual = schemes_service.list_active_schemes(db, language=language)
    return SchemesListResponse(
        language=actual,
        schemes=[
            SchemeSummary(
                key=s.key,
                name=t.name,
                icon=s.icon,
                state_scope=s.state_scope,
                sort_order=s.sort_order,
            )
            for s, t in rows
        ],
    )


@router.get("/{key}", response_model=SchemeDetail)
def get_scheme(
    key: str,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(db_session_dep)],
    language: str = Query(default="en"),
) -> SchemeDetail:
    _guard_language(language)
    scheme, translation, actual, fell_back = schemes_service.get_scheme_by_key(
        db, key=key, language=language,
    )
    if scheme is None or translation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active scheme '{key}'.",
        )
    docs = [SchemeDoc(**d) for d in (scheme.docs_needed or [])]
    return SchemeDetail(
        key=scheme.key,
        language=actual,
        name=translation.name,
        description=translation.description,
        apply_note=translation.apply_note,
        apply_url=scheme.apply_url,
        docs_needed=docs,
        estimated_time=scheme.estimated_time,
        state_scope=scheme.state_scope,
        icon=scheme.icon,
        language_fallback=fell_back,
    )


@router.post("/match", response_model=MatchResponse)
def match_schemes(
    profile: WorkerProfile,
    user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[Session, Depends(db_session_dep)],
    language: str = Query(default="en"),
) -> MatchResponse:
    _guard_language(language)
    matches, total, actual = schemes_service.match(
        db, profile=profile, language=language,
    )
    return MatchResponse(
        language=actual,
        matches=matches,
        total_candidates=total,
    )
