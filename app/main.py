












import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langsmith import traceable
from dotenv import load_dotenv

from app.config import get_settings
from app.models import (
    ChatRequest, ChatResponse,
    HealthResponse, MetricResponse, ErrorResponse,
)
from app.security import SecurityPipeline
from app.cache import ResponseCache
from app.monitoring import MetricsCollector, RequestTimer, get_logger
from app.agent import ProductionAgent

load_dotenv()


# Application components (initialized in lifespan)
security: SecurityPipeline = None
cache: ResponseCache = None
metrics: MetricsCollector = None
agent: ProductionAgent = None
logger = get_logger()




# === Lifespan (startup/shutdown) ===

@asynccontextmanager
async def lifespan (app: FastAPI):
    """
    Initialize all components on startup, clean up on shutdown.
    This is the modern FastAPI pattern (replaces @app.on_event).
    """
    global security, cache, metrics, agent
    settings = get_settings()

    logger.info("Starting production API...", extra={"extra_data": {
        "enviroment": settings.app_env,
        "live_model": settings.live_model, "primary_model": settings.primary_model, "secondary_model": settings.secondary_model, "fallback_model": settings.fallback_model, "is_production": settings.is_production,
        "tracing_enable": settings.langsmith_tracing_v2
    }})

    # Initialize components
    security = SecurityPipeline()
    cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
    metrics = MetricsCollector()
    agent = ProductionAgent()

    logger.info("All components initialized. Ready ro serve requests.")

    yield # App is running

    # Shutdown
    logger.info("Shutting down production API...", extra={"extra_data": metrics.summary})


# === Rate Limiter Setup ===
limiter = Limiter(key_func=get_remote_address)

# === FastAPI App ===
app = FastAPI(
    title="Production LangGraph API",
    description="A production ready chat API with security, caching, and observability.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter


# === Exception Handlers ===

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded exceptions."""
    return JSONResponse(
        status_code=429,
        content=ErrorResponse(
            error="Rate limit exceeded",
            detail=str(exc),
        ).model_dump(),
    )

# Handle other exceptions
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions."""
    logger.error("Unhandled exception", extra={"extra_data": {"error": str(exc)}})
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc),
        ).model_dump(),
    )

# ==============================
# ENDPOINTS
# ==============================

@app.post("/chat",response_model=ChatResponse, status_code=200)
@limiter.limit(get_settings().rate_limit)
@traceable(name="chat_endpoint")
async def chat(request: Request, body: ChatRequest):
    """
    Main chat endpoint

    Flow:
    1. Security check (injection + PII masking)
    2. Cache lookup
    3. LangGraph agent invoke (if cache miss)
    4. Output validation
    5. Cache store
    6. Return response
    """
    with RequestTimer() as timer:
        security_notes = []

    # ---- Step 1: Security check ----
    is_allowed, cleaned_message, notes = security.check_input(body.message)
    security_notes.extend(notes)

    if not is_allowed:
        logger.warning("Request blocked by security", extra={"extra_data": {
            "reason": notes,
            "thread_id": body.thread_id,
        }})
        metrics.record_request(latency_ms=0, error=True)
        raise HTTPException(
            status_code=400,
            detail="Your message was blocked by our security filters."
        )

    # ---- Step 2: Cache lookup ----
    if cache:
        cached_response = cache.get(cleaned_message)
        if cached_response:
            metrics.record_request(latency_ms=0, cache_hit=True)
            logger.info("Cache hit", extra={"extra_data": {
                "thread_id": body.thread_id,
            }})
            return ChatResponse(
                response=cached_response,
                thread_id=body.thread_id,
                model_used="cache",
                cache=True,
                processing_time_ms=0,
            )

    # ---- Step 3: Agent invocation ----

    try:
        result = await agent.invoke(cleaned_message)
    except Exception as e:
        logger.error(f"Agent invocation failed: {e}", extra={"extra_data": {
            "thread_id": body.thread_id,
            "error": str(e),
            }})
        metrics.record_request(latency_ms=0, error=True)
        raise HTTPException(
            status_code=500,
            detail="Error while processing your message. Please try again.",
        )
    response_text = result["response"]
    model_used = result["model_used"]
    is_fallback = result["is_fallback"]
    
    # ---- Step 4: Output validation ----
    validated_response, output_warnings = security.check_output(response_text)
    security_notes.extend(output_warnings)

    # ---- Step 5: Cache Store ----
    cache.set(cleaned_message, validated_response)

    # ---- Step 6: Metrics and Logging ----
    input_tokens = int(len(cleaned_message.split()) * 1.6)
    output_tokens = int(len(validated_response.split()) * 1.3)

    metrics.record_request(
        latency_ms=timer.elapsed_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_hit=False,
    )

    if security_notes:
        logger.info("Security notes", extra={"extra_data": {
            "notes": security_notes,
            "thread_id": body.thread_id,
        }})

    # ---- Step 7: Return response ----
    return ChatResponse(
        response=validated_response,
        thread_id=body.thread_id,
        model_used=model_used,
        cache=False,
        processing_time_ms=round(timer.elapsed_ms, 2),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check for Docker / Kubernetes."""
    settings = get_settings()

    checks = {
        "agent": agent is not None,
        "security": security is not None,
        "cache": cache is not None,
    }

    all_healthy = all(checks.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        enviroment=settings.app_env,
        components=checks,
        timestamp=datetime.utcnow().isoformat(),
    )

@app.get("/metrics", response_model=MetricResponse)
async def metrics():
    """Metrics for monitoring dashboards."""
    summary = metrics.summary
    return MetricResponse(**summary)

@app.get("/cache/stats")
async def cache_stats():
    """Cache performance statistics."""
    return cache.stats