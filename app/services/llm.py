import re

import httpx

from app.config import Settings

SYSTEM_PROMPT = (
    "You are an elite Enterprise Technology Architecture assistant. Analyze the provided technical text and return a summary consisting of EXACTLY 5 lines or bullet points. Focus strictly on architectural shifts, model routing, vector search data ingestion pipelines, orchestration rules, capabilities, and enterprise guardrails. Do not include introductory text, conversational filler, or formatting headers. Output exactly 5 high-density lines."
)


class SummaryGenerationError(RuntimeError):
    """Raised when Gemini cannot produce a valid architecture summary."""


def normalize_five_lines(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw_line).strip()
        if cleaned:
            lines.append(cleaned)
    if len(lines) != 5:
        raise SummaryGenerationError(f"LLM returned {len(lines)} lines; exactly 5 are required")
    return "\n".join(f"• {line}" for line in lines)


async def generate_summary(text: str, settings: Settings, client: httpx.AsyncClient) -> str:
    if not settings.llm_api_key:
        raise SummaryGenerationError("LLM_API_KEY is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent"
    )
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": text[: settings.max_article_chars]}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 700},
    }
    try:
        response = await client.post(
            url,
            params={"key": settings.llm_api_key},
            json=payload,
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        generated = data["candidates"][0]["content"]["parts"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise SummaryGenerationError("Gemini summary generation failed") from exc
    return normalize_five_lines(generated)
