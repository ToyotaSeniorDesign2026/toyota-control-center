from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.integrations import OpenAIChatRequest


def _build_transcript(payload: OpenAIChatRequest) -> str:
    transcript_lines: list[str] = []
    for message in payload.messages[-12:]:
        role = message.role.strip().lower() if message.role else "user"
        transcript_lines.append(f"{role.upper()}: {message.content}")
    return "\n".join(transcript_lines)


def _extract_output_text(response_json: dict) -> str:
    for item in response_json.get("output", []):
        for content_item in item.get("content", []):
            if content_item.get("type") == "output_text" and content_item.get("text"):
                return str(content_item["text"]).strip()
    return ""


def request_openai_chat(payload: OpenAIChatRequest) -> dict:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENAI_API_KEY is not configured on the backend.",
        )

    system_prompt = (
        "You are the Toyota Control Center user chatbot. "
        "Help users launch jobs from chat by asking one relevant next question at a time. "
        "Be concise, practical, and specific. "
        "When workflow_state or goal is provided, use it to shape the next assistant reply. "
        "Do not invent platform capabilities. "
        "Do not mention internal implementation details. "
        "Return plain text only."
    )

    composed_input = {
        "goal": payload.goal,
        "workflow_state": payload.workflow_state,
        "fallback_response": payload.fallback_response,
        "transcript": _build_transcript(payload),
    }

    body = {
        "model": settings.openai_model,
        "instructions": system_prompt,
        "input": json.dumps(composed_input, ensure_ascii=True),
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    _MAX_ATTEMPTS = 4
    response_json: dict = {}
    for attempt in range(_MAX_ATTEMPTS):
        try:
            with urlopen(request, timeout=settings.openai_timeout_seconds) as response:
                response_json = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            if exc.code == 429 and attempt < _MAX_ATTEMPTS - 1:
                raw = exc.read().decode("utf-8", errors="ignore")
                import re as _re
                wait_match = _re.search(r"try again in\s+([\d.]+)s", raw, _re.IGNORECASE)
                base_wait = float(wait_match.group(1)) if wait_match else 5.0
                wait = min(base_wait * (2 ** attempt), 60.0)
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The AI service is currently busy. Please wait a moment and try again.",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI request failed: {detail or exc.reason}",
            ) from exc
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"OpenAI connection failed: {exc.reason}",
            ) from exc

    content = _extract_output_text(response_json) or payload.fallback_response or ""
    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI response did not contain assistant text.",
        )

    return {
        "content": content,
        "model": str(response_json.get("model") or settings.openai_model),
        "response_id": response_json.get("id"),
    }
