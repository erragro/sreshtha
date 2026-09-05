"""OpenAI embedding wrapper.

One call site pattern: batch a list of strings, get back a list of
vectors of the requested dimensionality. Matryoshka reduction is done
by OpenAI's server-side via the ``dimensions`` parameter — the
returned vectors are the first N components of the full 3072-dim
representation, already re-normalised.

Handles rate-limit + transient error retries with exponential backoff.
No SDK dependency — the OpenAI embeddings surface is stable enough
that a direct HTTPS call is cheaper than pulling ``openai`` in.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Iterable

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


# Matches migration 013's ``vector(1024)`` column shape. Callers can
# override for future experiments (full 3072, small 1536) but the
# default has to match the DB column or inserts fail.
DEFAULT_MODEL = "text-embedding-3-large"
DEFAULT_DIMENSIONS = 1024

# OpenAI's embed endpoint accepts up to 2048 strings per request today.
# Keep well below that in case per-request byte limits kick in first.
_MAX_BATCH = 128


def embed(
    texts: Iterable[str],
    *,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[list[float]]:
    """Embed a list of strings. Returns one vector per input in the
    same order. Empty strings are embedded as zero-vectors of the same
    dimensionality (cheaper than dropping and re-indexing)."""
    items = list(texts)
    if not items:
        return []
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is unset. Retrieval embedding needs it."
        )

    out: list[list[float]] = []
    for i in range(0, len(items), _MAX_BATCH):
        batch = items[i : i + _MAX_BATCH]
        # Replace empty strings with a single space so OpenAI doesn't
        # 400; we'll zero the vector after.
        cleaned = [t if t.strip() else " " for t in batch]

        vecs = _call(model=model, inputs=cleaned, dimensions=dimensions)

        for text, vec in zip(batch, vecs):
            if not text.strip():
                out.append([0.0] * dimensions)
            else:
                out.append(vec)
    return out


def embed_one(
    text: str,
    *,
    model: str = DEFAULT_MODEL,
    dimensions: int = DEFAULT_DIMENSIONS,
) -> list[float]:
    """Convenience wrapper for single-query embed."""
    return embed([text], model=model, dimensions=dimensions)[0]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _call(
    *,
    model: str,
    inputs: list[str],
    dimensions: int,
) -> list[list[float]]:
    payload = {
        "model": model,
        "input": inputs,
        "dimensions": dimensions,
    }
    max_attempts = 4
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = httpx.post(
                f"{settings.openai_base_url.rstrip('/')}/embeddings",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                raise RuntimeError(
                    f"openai embeddings {resp.status_code}: {resp.text[:300]}"
                )
            resp.raise_for_status()
            data = resp.json()
            return [row["embedding"] for row in data["data"]]
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_attempts:
                delay = 0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.2)
                logger.warning(
                    "embedding attempt %d/%d failed: %s — sleeping %.1fs",
                    attempt, max_attempts, exc, delay,
                )
                time.sleep(delay)
                continue
            raise
    raise last_exc  # unreachable
