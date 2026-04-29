"""Chat service for AI-powered conversations using OpenAI."""

import json
import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_REGISTRY_PATH = (
    Path(__file__).parent.parent.parent
    / "src" / "control_center" / "core" / "registry" / "registry.json"
)


def _build_job_types_section() -> str:
    """Read registry.json and return a compact job-types reference for the system prompt."""
    try:
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
    except Exception:
        logger.warning("Could not load registry.json for system prompt")
        return ""

    lines: list[str] = []

    # Universal fields
    universal = registry.get("universal_job_fields", {})
    req = universal.get("required", [])
    opt = universal.get("optional", [])
    if req or opt:
        lines.append("UNIVERSAL FIELDS (every job type):")
        if req:
            lines.append(f"  Required: {', '.join(req)}")
        if opt:
            lines.append(f"  Optional: {', '.join(opt)}")
        lines.append("")

    # Per-connector job fields
    job_servers = {
        name: srv
        for name, srv in registry.get("approved_servers", {}).items()
        if srv.get("required_fields") is not None or srv.get("optional_fields") is not None
    }
    if job_servers:
        lines.append("CONNECTOR-SPECIFIC FIELDS:")
        for name, srv in job_servers.items():
            display = srv.get("display_name") or name
            job_type = srv.get("job_type", name)
            req = srv.get("required_fields") or []
            opt = srv.get("optional_fields") or []
            lines.append(f"  {display} (connector: {name}, job_type: {job_type}):")
            if req:
                lines.append(f"    Required: {', '.join(req)}")
            if opt:
                lines.append(f"    Optional: {', '.join(opt)}")

    return "\n".join(lines)


class ChatService:
    """Service for handling chat messages with AI."""

    def __init__(self):
        if not settings.openai_api_key:
            logger.warning("OpenAI API key not configured. Chat will not work.")
            self.client = None
        else:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                logger.error("OpenAI package not installed. Install with: pip install openai")
                self.client = None

    async def send_message(
        self,
        message: str,
        conversation_history: Optional[list] = None,
        model: Optional[str] = None,
        current_draft: Optional[dict] = None,
        available_resources: Optional[list] = None,
    ) -> str:
        if not self.client:
            return "Chat service is not properly configured. Please check OpenAI API key."

        try:
            model = model or settings.openai_model

            resources_list = (
                "\n".join(
                    f"- id={r['id']}  name={r['name']}  type={r.get('type', 'unknown')}"
                    for r in available_resources
                )
                if available_resources
                else "(none)"
            )

            draft_context = (
                f"\n\nCURRENT DRAFT:\n{json.dumps(current_draft, indent=2)}\n"
                "Ask for the next missing required field only. Do not re-ask filled fields."
                if current_draft
                else ""
            )

            system_prompt = f"""You are CC Assistant for the Toyota Control Center. \
Help users create, run, and manage jobs through a conversational UI.

{_build_job_types_section()}

RULES:
- Be concise and conversational. One question at a time.
- Collect universal fields first, then connector-specific fields.
- run_type="manual" means no schedule is needed.
- Never invent or assume field values. Never expose internal schemas.
- For SQL jobs: plain-English queries (e.g. "get all users") are valid — convert them to SQL.

AVAILABLE JOBS (existing resources the user can run):
{resources_list}

RUNNING EXISTING JOBS:
- If the user asks to run an existing job by name, find it above and append [RUN_JOB:<id>] at the end of your response.
- Do not ask for confirmation if intent is already clear.
- If the job does not exist, offer to create it.
{draft_context}"""

            messages = [{"role": "system", "content": system_prompt}]
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": message})

            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
