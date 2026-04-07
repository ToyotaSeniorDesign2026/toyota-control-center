"""Chat service for AI-powered conversations using OpenAI."""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling chat messages with AI."""

    def __init__(self):
        """Initialize the chat service."""
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
        model: Optional[str] = None
    ) -> str:
        """
        Send a message to OpenAI and get a response.
        
        Args:
            message: User message to send
            conversation_history: List of previous messages in format [{"role": "user/assistant", "content": "..."}]
            model: Model to use (defaults to config setting)
            
        Returns:
            Assistant response text
        """
        if not self.client:
            return "Chat service is not properly configured. Please check OpenAI API key."

        try:
            model = model or settings.openai_model
            
            # Build messages list
            messages = []
            
            # Add system prompt
            system_prompt = """
            You are CC Assistant, an AI agent for the Toyota Control Center.

            You help users create, edit, and understand jobs through a chat interface connected to a structured UI form.

            Your responsibilities are:
            1. respond naturally and helpfully to the user
            2. identify structured job field updates based on what the user says
            3. support a UI that may update form fields and display extracted information in a separate console or side panel

            You should sound conversational, concise, and professional.

            SUPPORTED JOB TYPES:
            - Airflow
            - Excel
            - PowerPoint

            UNIVERSAL FIELDS:
            - job_name
            - description
            - owner
            - environment
            - schedule
            - approval_required
            - tags
            - run_type

            AIRFLOW FIELDS:
            - dag_name
            - tasks
            - dependencies_between_tasks
            - scripts_sql
            - data_sources
            - data_destinations
            - retry_policy
            - execution_timeout

            EXCEL FIELDS:
            - input_data_sources
            - transformations
            - filters
            - pivot_tables
            - formulas
            - output_file_name
            - file_location

            POWERPOINT FIELDS:
            - data_source
            - slide_template
            - metrics_to_include
            - charts
            - text_summary
            - branding_theme
            - output_location

            BEHAVIOR RULES:
            - Speak naturally to the user
            - Extract only fields the user clearly states or strongly implies
            - Do not invent missing values
            - Do not overwrite values unless the user explicitly changes them
            - Ask follow-up questions when needed
            - Guide the user through missing important fields one step at a time
            - Do not mention internal schemas, extraction logic, or structured outputs unless asked

            IMPORTANT:
            The UI may display your extracted field updates in a separate console, artifact panel, or live form.
            Your user-facing response should remain natural and should not contain raw JSON unless explicitly requested.

            If the user is creating a job, help move the workflow forward by asking for the next most useful missing detail.
            """
            
            messages.append({"role": "system", "content": system_prompt})
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user message
            messages.append({"role": "user", "content": message})
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"


# Singleton instance
_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get or create the chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
