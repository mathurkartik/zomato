from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
# Groq has deprecated `llama3-8b-8192`. Use the latest recommended replacement.
DEFAULT_MODEL = "llama-3.1-8b-instant"
SUPPORTED_MODELS = {DEFAULT_MODEL}


@dataclass(frozen=True)
class GroqCallResult:
    ok: bool
    status_code: int | None
    error: str | None
    raw_text: str | None
    json_body: dict[str, Any] | None
    latency_ms: int
    tokens_used: int | None


def get_groq_api_key() -> str:
    """
    Load .env and validate GROQ_API_KEY.
    This function must never expose the full key in logs.
    """
    # groq_client.py lives in: M1/src/phase3/groq_client.py
    # We want: M1/.env
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dotenv_path = os.path.join(project_root, ".env")
    load_dotenv(dotenv_path=dotenv_path, override=False)

    api_key = os.environ.get("GROQ_API_KEY")
    detected = bool(api_key)
    last4 = api_key[-4:] if api_key else "none"
    print(f"[groq] api_key_detected={detected} last4={last4}")

    if not api_key:
        # Explicit requirement string from the user.
        raise RuntimeError("Missing GROQ_API_KEY in environment")

    return str(api_key).strip()


def validate_or_fallback_model(model: str | None) -> str:
    cfg_model = (model or "").strip()
    if cfg_model in SUPPORTED_MODELS:
        return cfg_model
    if cfg_model:
        print(f"[groq] Unsupported model '{cfg_model}', falling back to '{DEFAULT_MODEL}'")
    return DEFAULT_MODEL


def _extract_tokens_used(body: dict[str, Any] | None) -> int | None:
    if not body:
        return None
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    # OpenAI compatible: total_tokens is usually available.
    t = usage.get("total_tokens")
    if isinstance(t, int):
        return t
    return None


def call_groq_chat_completions(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
    extra_debug_context: str = "",
) -> GroqCallResult:
    model = validate_or_fallback_model(model)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    t0 = time.perf_counter()
    try:
        import httpx

        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(GROQ_CHAT_URL, headers=headers, content=json.dumps(payload))
        latency_ms = int((time.perf_counter() - t0) * 1000)

        status_code = resp.status_code
        text = resp.text
        if status_code >= 400:
            # Log the full error body (still not exposing key).
            snippet = text[:1200]
            err = f"HTTP {status_code} {extra_debug_context}".strip()
            print(f"[groq] call failed: {err} body_snippet={snippet}")
            return GroqCallResult(
                ok=False,
                status_code=status_code,
                error=snippet,
                raw_text=text,
                json_body=None,
                latency_ms=latency_ms,
                tokens_used=None,
            )

        try:
            body = resp.json()
        except Exception:
            snippet = text[:1200]
            print(f"[groq] JSON parse failed body_snippet={snippet}")
            return GroqCallResult(
                ok=False,
                status_code=status_code,
                error="Groq response was not valid JSON",
                raw_text=text,
                json_body=None,
                latency_ms=latency_ms,
                tokens_used=None,
            )

        # OpenAI compatible error format might still be inside json.
        if isinstance(body, dict) and body.get("error"):
            err_obj = body.get("error")
            msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            print(f"[groq] Groq returned error json message={msg}")
            return GroqCallResult(
                ok=False,
                status_code=status_code,
                error=msg,
                raw_text=text,
                json_body=body,
                latency_ms=latency_ms,
                tokens_used=_extract_tokens_used(body),
            )

        return GroqCallResult(
            ok=True,
            status_code=status_code,
            error=None,
            raw_text=text,
            json_body=body,
            latency_ms=latency_ms,
            tokens_used=_extract_tokens_used(body),
        )
    except Exception as e:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[groq] exception during call: {e}")
        return GroqCallResult(
            ok=False,
            status_code=None,
            error=str(e),
            raw_text=None,
            json_body=None,
            latency_ms=latency_ms,
            tokens_used=None,
        )
