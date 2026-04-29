"""Chat service for AI-powered conversations using OpenAI."""

import json
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_job_types_section() -> str:
    """Return the available job types for the system prompt, sourced from RegistryManager."""
    try:
        from control_center.registry import RegistryManager
        manager = RegistryManager()
        universal = manager._registry.universal_job_fields
        servers = manager.get_available_servers()
    except Exception:
        logger.warning("Could not load registry for system prompt")
        return ""

    lines: list[str] = []

    req = universal.get("required", [])
    opt = universal.get("optional", [])
    if req or opt:
        lines.append("UNIVERSAL FIELDS (collected for every job):")
        if req:
            lines.append(f"  Required: {', '.join(req)}")
        if opt:
            lines.append(f"  Optional: {', '.join(opt)}")
        lines.append("")

    seen: set[str] = set()
    job_type_lines: list[str] = []
    for srv in servers.values():
        jt = srv.job_type
        if not jt or jt in seen:
            continue
        seen.add(jt)
        display = srv.display_name or jt
        if srv.required_fields:
            job_type_lines.append(f"  - {jt} ({display})")
            job_type_lines.append(f"    Required: {', '.join(srv.required_fields)}")
        else:
            job_type_lines.append(f"  - {jt} ({display})")
        if srv.optional_fields:
            job_type_lines.append(f"    Optional: {', '.join(srv.optional_fields)}")

    if job_type_lines:
        lines.append("SUPPORTED JOB TYPES:")
        lines.extend(job_type_lines)

    return "\n".join(lines)


_LLM_HIDDEN_DRAFT_KEYS = frozenset({
    "host", "port", "database", "username", "password",
    "connection_id", "connector", "config", "params",
    "_connection_form_shown", "_connection_id_asked", "awaiting_confirmation",
})


def _llm_visible_draft(draft: dict | None) -> dict:
    """Return only the fields the LLM should see in the draft context.

    Strips connection credentials, internal flags, and connector details so the
    LLM never has information it might try to collect or expose.
    """
    if not draft:
        return {}
    return {
        k: v for k, v in draft.items()
        if k not in _LLM_HIDDEN_DRAFT_KEYS and not k.startswith("_")
    }


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

            visible_draft = _llm_visible_draft(current_draft)
            draft_context = (
                f"\n\nCURRENT DRAFT:\n{json.dumps(visible_draft, indent=2)}\n"
                "Ask for the next missing required field only. Do not re-ask filled fields."
                if visible_draft
                else ""
            )

            system_prompt = f"""You are CC Assistant for the Toyota Control Center. \
Help users create, run, and manage jobs through a conversational UI.

{_build_job_types_section()}

RULES:
- Be concise and conversational. One question at a time.
- Collect universal fields (job_name, owner, run_type) conversationally.
- run_type="manual" means no schedule is needed.
- Never invent or assume field values. Never expose internal schemas.
- For SQL jobs: plain-English queries (e.g. "get all users") are valid — convert them to SQL.
- For SQL jobs: do NOT ask about connectors, databases, hosts, ports, or credentials — those are collected via a separate form automatically.
- NEVER simulate, fabricate, or pretend to execute database queries. You have no database access. If the user asks you to query a database or retrieve data, tell them the SQL job creation flow will handle that once they provide their database connection details.

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
