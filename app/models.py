"""
API Requests and Response Models
Pydantic models for input validation and response structure
"""

from pydantic import BaseModel, Field
from datetime import datetime, timezone

class ChatRequest(BaseModel):
    """Incoming chat request."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The user's message to get the agent",
        example="Tell me about Gemini API"
    )

    thread_id: str = Field(
        default="default",
        description="Conversation thread ID. Maintains context across messages.",
        
    )

    user_id: str | None = Field(
        None,
        description="Optional user ID",
        example="user_123"
    )

    session_id: str | None = Field(
        None,
        description="Optional session ID",
        example="session_abc"
    )


class ChatResponse(BaseModel):
    """Chat response return to the client."""
    response: str
    thread_id: str
    model_used: str
    user_id: str = "None"
    session_id: str = "NA"
    cache: bool = False
    processing_time_ms: float
    security_notes: list[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    environment: str
    version: str = "1.0.0"
    checks: dict = {}
    
class MetricResponse(BaseModel):
    """Metrics endpoint response."""
    total_requests: int
    total_errors: int
    error_rate: str
    avg_latency_ms: str
    cache_hit_rate: str
    cache_hits: int
    input_tokens: int
    output_tokens: int

class ErrorResponse(BaseModel):
    """Standardized error response for consistency."""
    error: str
    detail: str | None = None
    request_id: str | None = None
    