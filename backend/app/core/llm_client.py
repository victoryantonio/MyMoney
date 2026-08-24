"""
Single gateway for all LLM calls via DeepSeek API (CODING_RULES §2.4, §2.9.B).

All text + vision model calls go through `call_llm()`. Model IDs are constants
defined here only — never hardcode model IDs in services/parsers.

Design:
  - Transport (HTTP, headers, timeouts) and the fallback chain live here.
  - `parser` callback lets callers plug schema validation into the retry loop:
    if `parser(content)` returns None, the next model in the chain is tried.
  - Prompt content stays in the caller's domain module (nlu_parser, future
    receipt_service) — this module owns transport/fallback, not domain prompts.
"""

from collections.abc import Callable
from typing import TypeVar

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()

# ── Model constants (single source of truth) ─────────────────────────────────
# Verified live against the DeepSeek API (HTTP 400 → lists valid names):
#   deepseek-v4-flash          → text, cheap, primary
#   deepseek-v4-pro            → text, fallback for resilience
#   deepseek-v4-flash-vision-exp → experimental vision model (Phase 5)
# NOTE: the VS Code client (chatLanguageModels.json) shows *display labels*
# like "DeepSeek-V4-Flash-0731", but the API rejects those — it only accepts
# the lowercase names above (case-sensitive, no date suffix).
# Primary text model first; the chain tries the next model only when the
# previous one errors or its output is rejected (REQUIREMENTS: fallback wajib).
TEXT_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"]

# Vision/OCR models (Phase 5 — reserved for now)
VISION_MODELS = ["deepseek-v4-flash-vision-exp"]

T = TypeVar("T")


async def call_llm(
    messages: list[dict],
    *,
    models: list[str],
    temperature: float = 0.0,
    parser: Callable[[str], T | None] | None = None,
) -> T | None:
    """
    Call DeepSeek with a fallback chain.

    Returns the result of `parser(content)` (or the raw content string when
    `parser` is None) on the first model whose response is accepted.
    Returns None when all models fail or every response is rejected —
    callers must handle None gracefully ("parsing gagal, coba lagi").
    """
    if not settings.deepseek_api_key:
        log.error("deepseek_api_key_missing")
        return None

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.deepseek_base_url}/chat/completions"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for model in models:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                content = _extract_content(response.json())
            except Exception as e:  # noqa: BLE001 — gateway must degrade gracefully
                log.warning("llm_call_error", model=model, error=str(e))
                continue

            if parser is None:
                return content
            result = parser(content)
            if result is not None:
                return result

    log.error("llm_all_models_failed")
    return None


def _extract_content(data: dict) -> str:
    """Pull the assistant message content and strip markdown fences."""
    content = data["choices"][0]["message"]["content"].strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()
