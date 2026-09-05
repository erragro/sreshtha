"""
LLM provider abstraction — keeps the 4-stage pipeline decoupled from any
single vendor SDK. The only call-site contract is `chat(...)` returning the
raw text of the assistant turn. Structured-JSON parsing stays in each stage.

Model roles:
  - "fast"  → cheap classifier (Stage 0)
  - "smart" → judgment + response (Stage 1, Stage 3)
"""

from __future__ import annotations

import json
import logging
import random
import time
from functools import lru_cache
from typing import Iterator, Protocol

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    def chat(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        schema: dict | None = None,
    ) -> str:
        """Return the raw response text. When ``schema`` is a JSON Schema
        dict, the provider engages its native structured-output mode
        (OpenAI ``response_format={type: json_schema}``; Vertex Gemini
        ``response_schema``) so the returned string is guaranteed to be
        JSON conforming to the schema — no code fences, no prose.
        Callers still json.loads() the string; schema-mode only removes
        parse failures, it does not decode."""
        ...

    def chat_stream(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Yield response text chunks as they arrive. Not every stage needs
        this — the callers that do (Stage 3 responder) use it to stream
        tokens to the client via SSE. Stage 0 / Stage 1 stay on chat()
        because they parse structured JSON and can't emit partials."""
        ...


class VertexAIProvider:
    """
    Calls Gemini through Vertex AI. Auth is Application Default
    Credentials — either ``GOOGLE_APPLICATION_CREDENTIALS`` pointing at
    a service-account JSON, or ``gcloud auth application-default
    login``. ``GOOGLE_CLOUD_PROJECT`` must have Vertex AI enabled and
    active billing.

    The AI Studio bare-key path (``GEMINI_API_KEY``) has been removed —
    that path is rate-limited and easy for Google to block. Vertex is
    the only Google reasoning path in Sreshtha now.
    """

    def __init__(
        self,
        *,
        project: str,
        location: str,
        fast_model: str,
        smart_model: str,
    ):
        from google import genai  # noqa: WPS433

        if not project:
            raise RuntimeError(
                "VertexAIProvider needs GOOGLE_CLOUD_PROJECT. Set it in .env "
                "and complete `gcloud auth application-default login` first."
            )
        self._client = genai.Client(
            vertexai=True, project=project, location=location,
        )
        self._auth_mode = "vertex"
        self._model_by_role = {"fast": fast_model, "smart": smart_model}

    def _resolve(self, role: str) -> str:
        return self._model_by_role.get(role, self._model_by_role["smart"])

    def chat(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        schema: dict | None = None,
    ) -> str:
        from google.genai import types  # noqa: WPS433
        from google.genai import errors  # noqa: WPS433

        model = self._resolve(role)

        # Gemini 2.5-family "thinking" adds 5-15s per Stage 1/3 call and
        # buys us nothing here — deterministic Stage 2 validates every
        # action set the LLM proposes anyway, so extra internal reasoning
        # is a latency tax on decisions we then override in Python.
        # thinking_budget=0 turns it off. flash-lite ignores this
        # (thinking is off by default there), flash + pro honour it.
        thinking_off = types.ThinkingConfig(thinking_budget=0)

        # Vertex Gemini uses response_schema + response_mime_type to
        # enforce JSON output — same guarantee as OpenAI Structured
        # Outputs, different field names. Only engages when caller
        # passes a schema.
        config_kwargs = dict(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=thinking_off,
        )
        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = schema
        config = types.GenerateContentConfig(**config_kwargs)

        max_attempts = 4
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._client.models.generate_content(
                    model=model, contents=user, config=config,
                )
                return resp.text or ""
            except errors.APIError as exc:
                last_exc = exc
                status = getattr(exc, "code", None)
                if status == 429 or (status and 500 <= status < 600):
                    delay = min(16.0, (2 ** attempt) + random.uniform(0, 1))
                    logger.warning(
                        "vertex ai %s on attempt %d/%d; sleeping %.1fs",
                        status, attempt, max_attempts, delay,
                    )
                    time.sleep(delay)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError("vertex ai: retries exhausted")

    def chat_stream(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Streams text chunks via the google-genai SDK's server-sent
        streaming endpoint. Skips retry — the client is holding a
        real-time SSE connection open and a mid-stream retry would
        replay tokens the user already saw. On failure we let the
        exception bubble; the pipeline degrades to escalate."""
        from google.genai import types  # noqa: WPS433

        model = self._resolve(role)
        thinking_off = types.ThinkingConfig(thinking_budget=0)
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=thinking_off,
        )

        stream = self._client.models.generate_content_stream(
            model=model, contents=user, config=config,
        )
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text


class SarvamProvider:
    """
    Sarvam AI's OpenAI-compatible chat completions endpoint. Used for every
    detected language outside Gemini's {en, hi} — see language_detector.py
    for the routing rule.
    """

    def __init__(self, api_key: str, fast_model: str, smart_model: str):
        self._api_key = api_key
        self._model_by_role = {"fast": fast_model, "smart": smart_model}
        self._client = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))

    def _resolve(self, role: str) -> str:
        return self._model_by_role.get(role, self._model_by_role["smart"])

    def _post_with_retry(self, body: dict, headers: dict, max_attempts: int = 4) -> dict:
        url = "https://api.sarvam.ai/v1/chat/completions"
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._client.post(url, json=body, headers=headers)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    retry_after = resp.headers.get("retry-after")
                    if retry_after and retry_after.isdigit():
                        delay = min(20.0, float(retry_after))
                    else:
                        delay = min(16.0, (2 ** attempt) + random.uniform(0, 1))
                    logger.warning(
                        "sarvam %s on attempt %d/%d; sleeping %.1fs",
                        resp.status_code, attempt, max_attempts, delay,
                    )
                    time.sleep(delay)
                    continue
                if resp.status_code == 400:
                    # Log the body so we can see the actual rejection
                    # reason (model deprecated, max_tokens too high,
                    # message too long, etc). The HTTPStatusError below
                    # doesn't include the response body by default.
                    logger.error(
                        "sarvam 400: model=%s max_tokens=%s response=%s",
                        body.get("model"),
                        body.get("max_tokens"),
                        resp.text[:800],
                    )
                resp.raise_for_status()
                return resp.json()
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                delay = min(16.0, (2 ** attempt) + random.uniform(0, 1))
                logger.warning(
                    "sarvam transport error on attempt %d/%d (%s); sleeping %.1fs",
                    attempt, max_attempts, type(exc).__name__, delay,
                )
                time.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("sarvam: retries exhausted")

    def chat(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str:
        body = {
            "model": self._resolve(role),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            # Clamp to the subscription-tier cap. Starter tier is 4096;
            # requests above that fail with a 400 "exceeds subscription
            # tier limit". Callers can safely pass their preferred budget
            # (e.g. 8192 for Stage 1/3) without knowing the tier.
            "max_tokens": min(max_tokens, settings.sarvam_max_tokens_cap),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        data = self._post_with_retry(body, headers)
        choices = data.get("choices") if isinstance(data, dict) else None
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content
            # Reasoning models (sarvam-105b, not -conversations) may
            # return content=null when max_tokens ran out on internal
            # reasoning_content. Fall back to that so downstream parsers
            # at least get something to work with, even if malformed.
            reasoning = msg.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                logger.warning(
                    "Sarvam returned reasoning_content only (content was empty). "
                    "Switch to sarvam-105b-conversations for cleaner output."
                )
                return reasoning
        logger.warning("Sarvam returned unexpected shape: %r", str(data)[:300])
        return ""

    def chat_stream(
        self,
        *,
        role: str,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> Iterator[str]:
        """Sarvam ships an OpenAI-compatible streaming SSE endpoint. We
        POST with stream=true, iterate over `data: {...}` frames, and
        yield the delta content of each. Same no-retry policy as the
        Vertex stream — the client is holding a real-time connection."""
        body = {
            "model": self._resolve(role),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        url = "https://api.sarvam.ai/v1/chat/completions"
        with self._client.stream("POST", url, json=body, headers=headers) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw or not raw.startswith("data: "):
                    continue
                payload = raw[len("data: "):]
                if payload.strip() == "[DONE]":
                    break
                try:
                    frame = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = frame.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text


class OpenAIProvider:
    """
    Calls the OpenAI Chat Completions API (or an OpenAI-compatible base
    URL). Kept HTTP-level rather than through the ``openai`` SDK so we
    do not pull another dependency; the surface we use — a POST to
    ``/chat/completions`` with a Bearer token — is stable across
    versions.

    Roles map to two configured model ids:
      "fast"  → settings.openai_fast_model  (Stage 0 classifier, cheap)
      "smart" → settings.openai_smart_model (Stage 1 evaluator, Stage 3
                                             responder, Contract Reader
                                             Stages 1-3)
    """

    def __init__(self, *, api_key: str, base_url: str,
                 fast_model: str, smart_model: str):
        if not api_key:
            raise RuntimeError("OpenAIProvider needs OPENAI_API_KEY.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_by_role = {"fast": fast_model, "smart": smart_model}

    def _resolve(self, role: str) -> str:
        return self._model_by_role.get(role, self._model_by_role["smart"])

    def _post(self, payload: dict) -> httpx.Response:
        return httpx.post(
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def chat(self, *, role: str, system: str, user: str,
             max_tokens: int = 1024, temperature: float = 0.2,
             schema: dict | None = None) -> str:
        model = self._resolve(role)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # OpenAI Structured Outputs — 100% schema match when the model
        # supports it (gpt-4o family). Requires strict=True + additional
        # required-field constraints on the schema itself; callers pre-
        # bake those. We just wire the plumbing.
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.get("name", "response"),
                    "strict": True,
                    "schema": schema.get("schema", schema),
                },
            }
        max_attempts = 4
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._post(payload)
                # Retry on rate limits and server errors; anything else
                # raises immediately.
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(
                        f"openai {resp.status_code}: {resp.text[:300]}"
                    )
                resp.raise_for_status()
                body = resp.json()
                return body["choices"][0]["message"]["content"] or ""
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < max_attempts:
                    time.sleep(0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.2))
                    continue
                raise
        raise last_exc  # unreachable

    def chat_stream(self, *, role: str, system: str, user: str,
                    max_tokens: int = 1024,
                    temperature: float = 0.2) -> Iterator[str]:
        model = self._resolve(role)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        with httpx.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(120.0, connect=10.0),
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


def _resolve_selection() -> str:
    """Which reasoning provider to instantiate.

    OpenAI is the default for local testing. Vertex AI (Gemini) is the
    explicit backup — set ``LLM_PROVIDER=vertex`` to route through it.
    ``LLM_PROVIDER=gemini`` is accepted as an alias for ``vertex`` for
    now to avoid breaking any docs.
    """
    choice = (settings.llm_provider or "").strip().lower()
    if choice in ("vertex", "gemini"):
        return "vertex"
    # "" and "openai" both mean OpenAI.
    return "openai"


@lru_cache(maxsize=4)
def get_provider(language: str = "en", provider: str | None = None) -> LLMProvider:
    """Return the LLM provider for the given language.

    Architecture (as of the per-stage hybrid, 2026-09):
      - Stage 1 (extract) explicitly uses OpenAI ``gpt-4o-mini`` — see
        ``app/contracts/stage1.py``.
      - Stage 2 (annotate) explicitly uses OpenAI ``gpt-4o`` + RAG.
      - Stage 3 (rewrite) explicitly uses Vertex AI Gemini for warmer
        tone before Mayura translation — see ``app/contracts/stage3.py``.
      - Cardinal chat pipeline defaults follow ``LLM_PROVIDER`` env var
        (default OpenAI).
      - Sarvam Mayura owns Indic translation regardless.

    Callers can force a specific provider by passing
    ``provider="openai"`` or ``provider="vertex"``. If ``provider`` is
    None the ``LLM_PROVIDER`` env selector is honoured.
    """
    _ = language  # reserved for future per-language routing
    if provider is None:
        selection = _resolve_selection()
    else:
        p = provider.strip().lower()
        selection = "vertex" if p in ("vertex", "gemini") else "openai"

    if selection == "openai":
        logger.info("get_provider: routing to OpenAI")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            fast_model=settings.openai_fast_model,
            smart_model=settings.openai_smart_model,
        )
    logger.info("get_provider: routing to Vertex AI (%s)", settings.gemini_smart_model)
    return VertexAIProvider(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        fast_model=settings.gemini_fast_model,
        smart_model=settings.gemini_smart_model,
    )
