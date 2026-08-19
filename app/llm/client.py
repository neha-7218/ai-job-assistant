"""LLM client wrapper — Gemini (primary) or OpenAI (fallback)."""

import json
import logging
import re

from app.config import get_settings

log = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """Parse JSON from LLM output, stripping markdown fences if present."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return json.loads(cleaned)


def _call_gemini(system: str, user: str) -> str:
    import google.generativeai as genai

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not set. Add it to .env")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        settings.model,
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config={
            "temperature": 0.3,
            "response_mime_type": "application/json",
        },
    )
    return response.text


def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set. Add it to .env")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.model if settings.model.startswith("gpt") else "gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or "{}"


def complete_json(system: str, user: str) -> dict:
    """Call the configured LLM and return parsed JSON. Retries once on parse failure."""
    settings = get_settings()
    caller = _call_openai if settings.llm_provider == "openai" else _call_gemini

    last_error = None
    for attempt in range(2):
        try:
            raw = caller(system, user)
            return _extract_json(raw)
        except (json.JSONDecodeError, ValueError) as error:
            last_error = error
            user = user + "\n\nReturn ONLY valid JSON. No markdown, no extra text."
            log.warning("JSON parse failed (attempt %s), retrying", attempt + 1)

    raise ValueError(f"LLM returned invalid JSON: {last_error}")
