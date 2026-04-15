"""Service for extracting job fields from user messages using LLM."""

import json
import logging
from typing import Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class FieldExtractionService:
    """Service for extracting structured job fields from chat messages."""

    def __init__(self):
        """Initialize the extraction service."""
        if not settings.openai_api_key:
            self.client = None
        else:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                self.client = None

    async def extract_fields(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        current_draft: Optional[dict] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Extract job-related fields from a user message.
        
        Args:
            user_message: The user's input message
            conversation_history: Previous conversation messages
            current_draft: Current draft job data (to avoid overwriting)
            model: LLM model to use
            
        Returns:
            Dictionary of extracted fields (only fields that should be updated)
        """
        if not self.client:
            return {}

        try:
            model = model or settings.openai_model
            
            # Build extraction prompt
            extraction_prompt = self._build_extraction_prompt(user_message, current_draft)
            
            # Build messages for LLM
            messages = []
            
            if conversation_history:
                messages.extend(conversation_history)
            
            messages.append({"role": "user", "content": extraction_prompt})
            
            # Call LLM to extract fields
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,  # Lower temperature for consistent extraction
                max_tokens=500,
            )
            
            response_text = response.choices[0].message.content
            
            # Parse the JSON response
            extracted = self._parse_extraction_response(response_text)
            
            return extracted
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}")
            return {}

    def _build_extraction_prompt(self, user_message: str, current_draft: Optional[dict] = None) -> str:
        """Build the prompt for field extraction."""
        
        current_state = ""
        if current_draft:
            current_state = f"\n\nCurrent draft state:\n{json.dumps(current_draft, indent=2)}"
        
        return f"""You are a field extraction assistant. Your job is to extract job configuration fields from user messages.

INSTRUCTIONS:
1. Parse the user message for any explicitly stated job fields
2. Return ONLY fields that the user clearly mentioned or strongly implied
3. Do NOT invent or assume values for fields not mentioned
4. Use the exact field names provided
5. Return an empty object if nothing to extract
6. Return response as valid JSON only, no other text

IMPORTANT:
- When extracting job_type, recognize variations like "sql", "SQL", "query" → "SQL", "powerpoint", "PowerPoint", "ppt" → "PowerPoint", "excel", "Excel", "xls" → "Excel", "airflow", "Airflow", "dag" → "Airflow"
- When extracting owner, recognize patterns like "I'm the owner", "I am the owner", "im the owner" → extract user as owner or use literal email if provided
- For schedule, accept natural language like "daily", "weekly monday", "every monday at 3am"
- For SQL resources, prefer backend-aligned fields when possible:
  - name, kind, type, connector, environment, data_sensitivity, tags
  - config.query, config.connection_id, config.schedule
  - action, target_environment, params.query for run-specific overrides
- For the local Control Center database, use connector "sql-dab" and connection_id "postgres" unless the user says otherwise
- If the user says the job should run manually, extract run_type as "manual" and do not invent a schedule

SUPPORTED FIELDS:

Universal Fields:
- job_name (string)
- description (string)
- owner (string, email format or name)
- environment (string: dev, staging, prod, production)
- schedule (string: cron or natural language like "daily at 7am", "every Monday")
- approval_required (boolean: true/false)
- tags (array of strings)
- run_type (string: manual, scheduled, triggered)
- job_type (string: "SQL", "Airflow", "Excel", "PowerPoint")
- action (string: usually "run")
- target_environment (string: dev, staging, prod, production)

Backend resource fields:
- name (string)
- kind (string: "runtime" or "artifact")
- type (string: "sql", "research", "agent", "airflow_dag", "dbt_job", "pipeline", "bi_task", "powerbi_report", "excel_task", "powerpoint_task", "report")
- connector (string)
- data_sensitivity (string: low, medium, high, public, internal, confidential)
- config (object)
- params (object)

SQL-specific backend fields:
- query (string)
- connection_id (string)
- output_destination (string)
- result_limit (string or number)

Airflow-specific:
- dag_name (string)
- tasks (array of strings)
- dependencies_between_tasks (string)
- scripts_sql (string)
- data_sources (array of strings)
- data_destinations (array of strings)
- retry_policy (string)
- execution_timeout (string: like "30m", "1h")

Excel-specific:
- input_data_sources (array of strings)
- transformations (string)
- filters (string)
- pivot_tables (boolean)
- formulas (string)
- output_file_name (string)
- file_location (string)

PowerPoint-specific:
- data_source (string)
- slide_template (string)
- metrics_to_include (array of strings)
- charts (array of strings)
- text_summary (string)
- branding_theme (string)
- output_location (string)

EXTRACTION EXAMPLES:
- User: "Create a PowerPoint named Revenue Dashboard"
  → {{"job_name": "Revenue Dashboard", "job_type": "PowerPoint"}}
- User: "Create a SQL resource called Dealer Sales Summary in dev using Snowflake"
  → {{"job_type": "SQL", "name": "Dealer Sales Summary", "kind": "runtime", "type": "sql", "environment": "dev", "connector": "snowflake"}}
- User: "Use this query as the default query and schedule it daily at 6am"
  → {{"config": {{"query": "USER_PROVIDED_QUERY", "schedule": "daily at 6am"}}}}
- User: "For this run, override the query to only pull yesterday's rows"
  → {{"action": "run", "params": {{"query": "QUERY_OVERRIDE_FOR_THIS_RUN"}}}}
- User: "Run the registered SQL resource dealer_sales_summary"
  → {{"job_type": "SQL", "action": "run", "name": "dealer_sales_summary"}}
- User: "Run dealer_sales_summary with query select * from sales limit 10"
  → {{"job_type": "SQL", "action": "run", "name": "dealer_sales_summary", "query": "select * from sales limit 10"}}
- User: "I want to get all the runs from the control-center database"
  → {{"job_type": "SQL", "connector": "sql-dab", "connection_id": "postgres", "query": "SELECT * FROM runs"}}
- User: "please run it manually"
  → {{"run_type": "manual"}}
- User: "Extract data from Snowflake table customers"
  → {{"data_sources": ["Snowflake table customers"]}}
- User: "Im the owner and schedule it for monday at 3am"
  → {{"owner": "user", "schedule": "every Monday at 3am"}}
- User: "Add metrics like revenue, growth, and margin"
  → {{"metrics_to_include": ["revenue", "growth", "margin"]}}

USER MESSAGE:
"{user_message}"{current_state}

Extract fields as JSON. Return ONLY valid JSON, no markdown, no explanation.

For SQL resource setup, prefer backend-aligned shapes such as:
- {{"name": "...", "kind": "runtime", "type": "sql", "connector": "...", "environment": "dev", "config": {{"query": "...", "connection_id": "...", "schedule": "..."}}}}
- use params.query only when the user clearly means a run-specific override rather than the resource default.

Use normalized field names like "SQL", "PowerPoint", and convert schedule descriptions to the schedule field."""

    def _parse_extraction_response(self, response_text: str) -> dict[str, Any]:
        """Parse the JSON extraction response from LLM."""
        try:
            # Try to find JSON in the response (in case there's extra text)
            response_text = response_text.strip()
            if response_text.startswith("```"):
                # Remove markdown code blocks if present
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            extracted = json.loads(response_text)
            
            # Validate and clean the extracted data
            if not isinstance(extracted, dict):
                return {}
            
            # Remove any fields that have None or empty string values
            cleaned = {k: v for k, v in extracted.items() if v is not None and v != ""}
            
            return cleaned
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse extraction JSON: {response_text}")
            return {}


# Singleton instance
_extraction_service: Optional[FieldExtractionService] = None


def get_field_extraction_service() -> FieldExtractionService:
    """Get or create the field extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = FieldExtractionService()
    return _extraction_service
