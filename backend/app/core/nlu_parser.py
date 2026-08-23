"""
Natural Language Understanding (NLU) Parser via OpenRouter (GLM-5.2 or Fallbacks).
Transforms raw text from Telegram into a structured JSON for transactions.
"""

import json
from decimal import Decimal
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

from app.core.config import settings

log = structlog.get_logger()

class ParsedTransaction(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: Decimal = Field(gt=0)
    category: str
    note: str | None = None

_SYSTEM_PROMPT = """You are a financial assistant for 'MyMoney' app.
Extract transaction details from the user's text into JSON.
Today's currency is IDR (Rupiah). Assume standard abbreviations (e.g. 50k = 50000, 35rb = 35000).

Respond ONLY with a valid JSON object, no markdown formatting, no backticks, no explanations.
Schema:
{
  "type": "expense" or "income",
  "amount": number (exact numeric value, e.g. 35000),
  "category": string (a short 1-2 word category name, e.g. "Food", "Transport", "Salary"),
  "note": string (optional, what it was for, e.g. "Makan siang padang")
}

If you cannot parse it or it's not a transaction, return {"error": "unrecognized"}
"""

async def parse_text_to_transaction(text: str) -> ParsedTransaction | None:
    """
    Calls OpenRouter to parse the user's chat message into structured data.
    Returns ParsedTransaction on success, None if parsing fails or input is unrecognized.
    """
    if not settings.openrouter_api_key:
        log.error("openrouter_api_key_missing")
        return None

    # Priority model: GLM-5.2 Free. Fallback: Llama 3.3 70B Instruct Free.
    models_to_try = [
        "z-ai/glm-5.2:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "openrouter/free"
    ]

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.app_base_url,
        "X-Title": "MyMoney Bot",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.0,  # enforce deterministic output
            }
            try:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
                content = data["choices"][0]["message"]["content"].strip()
                
                # Cleanup potential markdown artifacts just in case the LLM disobeys
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                parsed_json = json.loads(content.strip())
                
                if "error" in parsed_json:
                    log.info("nlu_parse_unrecognized", text=text, model=model)
                    return None

                return ParsedTransaction(**parsed_json)

            except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
                log.warning("nlu_parse_error", model=model, error=str(e))
                continue  # Try next model

    log.error("nlu_parse_all_models_failed", text=text)
    return None
