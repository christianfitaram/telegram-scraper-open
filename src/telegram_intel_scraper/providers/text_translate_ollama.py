from __future__ import annotations

import json
from typing import NamedTuple

import requests

from telegram_intel_scraper.utils.text import normalize_whitespace


class ScraperResult(NamedTuple):
    language: str
    english_text: str
    title: str


def _parse_json_payload(payload: str) -> dict:
    cleaned = payload.strip()
    if not cleaned:
        raise ValueError("Empty Ollama response")

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def detect_translate_and_title_ollama(
    text: str,
    ollama_url: str,
    ollama_model: str,
    timeout: int = 60,
) -> ScraperResult:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return ScraperResult("unknown", "", "Empty Content")

    prompt = (
        "You detect the source language, translate text to English, and create a concise title.\n"
        "Return ONLY valid JSON with this shape:\n"
        '{"language":"string","english_text":"string","title":"string"}\n'
        "If the input is already English, preserve the meaning in english_text.\n"
        "Keep the title under 12 words.\n\n"
        f"Text:\n{cleaned[:12000]}"
    )

    response = requests.post(
        ollama_url,
        json={
            "model": ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=timeout,
    )
    response.raise_for_status()

    payload = (response.json().get("response") or "").strip()
    data = _parse_json_payload(payload)

    language = str(data.get("language", "unknown")).strip() or "unknown"
    english_text = normalize_whitespace(str(data.get("english_text", cleaned)).strip()) or cleaned
    title = normalize_whitespace(str(data.get("title", "Telegram message")).strip()) or "Telegram message"

    return ScraperResult(
        language=language,
        english_text=english_text,
        title=title[:120],
    )
