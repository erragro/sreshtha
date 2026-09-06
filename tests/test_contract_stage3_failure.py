"""Regression coverage for Stage 3 failure reporting and provider selection."""

from app.contracts import stage3
from app.contracts.stage3 import _chunk_failure_error


def test_failed_stage3_chunk_is_reported_as_retryable_error():
    error = _chunk_failure_error([1], {"clause_6", "clause_7"})

    assert error is not None
    assert "2 clause(s)" in error
    assert "retry" in error.lower()


def test_stage3_safe_fallback_does_not_create_chunk_error():
    assert _chunk_failure_error([], {"clause_1"}) is None


def test_stage3_generator_uses_the_configured_provider(monkeypatch):
    expected = object()
    calls: list[tuple[str, str | None]] = []

    def fake_get_provider(language: str, provider: str | None = None):
        calls.append((language, provider))
        return expected

    monkeypatch.setattr(stage3, "get_provider", fake_get_provider)

    assert stage3._get_generator_provider() is expected
    assert calls == [("en", None)]
