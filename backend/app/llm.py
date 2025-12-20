from __future__ import annotations

from typing import Dict, List, Optional
import requests

from app.settings import settings


class LLMError(RuntimeError):
    pass


def chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    provider = (settings.llm_provider or "").strip().lower()
    if provider == "groq":
        return _groq_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
    raise LLMError(f"Unsupported LLM provider: {provider}")


def _groq_chat_completion(
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    if not settings.groq_api_key:
        raise LLMError("GROQ_API_KEY is not set")

    url = f"{settings.groq_base_url.rstrip('/')}/chat/completions"
    payload: Dict[str, object] = {
        "model": settings.groq_model,
        "messages": messages,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    except Exception as exc:
        raise LLMError("Unexpected Groq response format") from exc
