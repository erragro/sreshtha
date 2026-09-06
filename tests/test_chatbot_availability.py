"""The legacy food-delivery chatbot must remain unavailable to workers."""

import pytest
from fastapi import HTTPException

from app.config import settings
from app.sessions.routes import _require_chatbot_enabled


def test_chatbot_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "chatbot_enabled", False)

    with pytest.raises(HTTPException) as exc_info:
        _require_chatbot_enabled()

    assert exc_info.value.status_code == 503
    assert "temporarily unavailable" in str(exc_info.value.detail)
