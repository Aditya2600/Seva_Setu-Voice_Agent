from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import requests
from requests import Response

from app.settings import settings

logger = logging.getLogger("sevasetu")


class LLMError(RuntimeError):
    pass


def _validate_messages(messages: List[Dict[str, str]]) -> None:
    if not isinstance(messages, list) or not messages:
        raise LLMError("messages must be a non-empty list of {role, content} dicts")
    for i, m in enumerate(messages):
        if not isinstance(m, dict):
            raise LLMError(f"messages[{i}] must be a dict")
        role = m.get("role")
        content = m.get("content")
        if role not in {"system", "user", "assistant"}:
            raise LLMError(f"messages[{i}].role must be one of system|user|assistant")
        if content is None or not str(content).strip():
            raise LLMError(f"messages[{i}].content must be a non-empty string")


def chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """Simple provider switch.

    Currently supported:
      - groq (GroqCloud OpenAI-compatible endpoint)

    If settings.llm_provider is empty/none, we raise a clear error so callers can fallback.
    """
    _validate_messages(messages)

    provider = (getattr(settings, "llm_provider", "") or "").strip().lower()
    if provider in {"", "none", "disabled", "off"}:
        raise LLMError("LLM is disabled (set LLM_PROVIDER=groq to enable)")

    logger.debug("LLM chat request provider=%s messages=%d", provider, len(messages))

    if provider in {"groq", "groqcloud"}:
        return _groq_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)

    raise LLMError(f"Unsupported LLM provider: {provider}")


def _timeout_seconds() -> float:
    # Optional: allow settings.llm_timeout_seconds
    t = getattr(settings, "llm_timeout_seconds", None)
    try:
        if t is not None:
            return float(t)
    except Exception:
        pass
    return 30.0


def _raise_for_bad_status(resp: Response) -> None:
    if 200 <= resp.status_code < 300:
        return
    snippet = ""
    try:
        snippet = (resp.text or "")[:500]
    except Exception:
        snippet = ""
    raise LLMError(f"Groq API error {resp.status_code}: {snippet}")


def _groq_chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    if not getattr(settings, "groq_api_key", ""):
        raise LLMError("GROQ_API_KEY is not set")

    base_url = (getattr(settings, "groq_base_url", "") or "").rstrip("/")
    if not base_url:
        raise LLMError("GROQ_BASE_URL is not set")

    model = getattr(settings, "groq_model", None) or ""
    if not model.strip():
        raise LLMError("GROQ_MODEL is not set")

    url = f"{base_url}/chat/completions"
    logger.debug("Groq request url=%s model=%s", url, model)

    payload: Dict[str, object] = {
        "model": model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    # Small retry for transient failures (network hiccups, 5xx)
    attempts = 2
    last_exc: Optional[Exception] = None
    for n in range(attempts):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=_timeout_seconds())
            if resp.status_code >= 500 and n < attempts - 1:
                # brief backoff
                time.sleep(0.6)
                continue
            _raise_for_bad_status(resp)
            data = resp.json()
            content = (
                (data.get("choices") or [{}])[0]
                .get("message", {})
                .get("content", "")
                or ""
            )
            logger.debug("Groq response chars=%d", len(content))
            return content
        except requests.RequestException as exc:
            last_exc = exc
            if n < attempts - 1:
                time.sleep(0.6)
                continue
        except ValueError as exc:
            # JSON parse error
            raise LLMError("Groq response was not valid JSON") from exc
        except Exception as exc:
            last_exc = exc

    raise LLMError("Groq request failed") from last_exc
