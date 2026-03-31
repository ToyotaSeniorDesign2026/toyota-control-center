"""Chat API router for handling AI chat messages."""

from typing import Optional, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.chat_service import get_chat_service
from app.services.field_extraction_service import get_field_extraction_service

router = APIRouter()


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    conversation_history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None
    current_draft_data: Optional[dict[str, Any]] = None  # Current job draft state


class ChatResponse(BaseModel):
    """Response from chat API."""
    response: str
    job_creation_intent: Optional[bool] = None  # True if user wants to create a job
    extracted_fields: Optional[dict[str, Any]] = None  # Extracted job fields from message


@router.post("/send", response_model=ChatResponse)
async def send_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Send a message to the AI chat assistant.
    
    Args:
        request: Chat request with message and optional conversation history
        
    Returns:
        AI assistant response with optional job creation intent and extracted fields
    """
    try:
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Detect job creation intent from user message
        job_creation_intent = detect_job_creation_intent(request.message)
        
        # Convert conversation history to dict format if provided
        history = None
        if request.conversation_history:
            history = [{"role": msg.role, "content": msg.content} for msg in request.conversation_history]
        
        chat_service = get_chat_service()
        response = await chat_service.send_message(
            message=request.message,
            conversation_history=history,
            model=request.model
        )
        
        # Extract job fields if this is not just the initial create-job intent trigger
        extracted_fields = None
        if not job_creation_intent:  # Only extract if not the create-job trigger message
            extraction_service = get_field_extraction_service()
            extracted_fields = await extraction_service.extract_fields(
                user_message=request.message,
                conversation_history=history,
                current_draft=request.current_draft_data,
                model=request.model
            )
            # Only include extracted_fields if there are any
            if not extracted_fields:
                extracted_fields = None
        
        return ChatResponse(
            response=response,
            job_creation_intent=job_creation_intent,
            extracted_fields=extracted_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


def detect_job_creation_intent(user_message: str) -> bool:
    """
    Detect if user is expressing intent to create a job.
    
    Args:
        user_message: The user's input message
        
    Returns:
        True if job creation intent is detected, False otherwise
    """
    message_lower = user_message.lower().strip()
    
    # Keywords that indicate job creation intent
    creation_keywords = [
        "create",
        "new job",
        "start a job",
        "build a job",
        "set up a job",
        "make a job",
        "add a job",
        "design a job",
    ]
    
    # Check if message contains creation-related keywords
    for keyword in creation_keywords:
        if keyword in message_lower:
            # Also check that it's about a job
            if "job" in message_lower or "workflow" in message_lower:
                return True
    
    return False
