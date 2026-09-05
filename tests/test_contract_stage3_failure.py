"""Regression coverage for Stage 3 chunk-failure reporting."""

from app.contracts.stage3 import _chunk_failure_error


def test_failed_stage3_chunk_is_reported_as_retryable_error():
    error = _chunk_failure_error([1], {"clause_6", "clause_7"})

    assert error is not None
    assert "2 clause(s)" in error
    assert "retry" in error.lower()


def test_stage3_safe_fallback_does_not_create_chunk_error():
    assert _chunk_failure_error([], {"clause_1"}) is None
