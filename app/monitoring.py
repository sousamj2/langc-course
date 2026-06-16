"""
Monitoring & Structure Logging
Production-grade metrics collection and JSON logging.
"""

import logging
import json
import time
from datetime import datetime,timezone
from functools import wraps
from typing import Callable, Any

class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for log aggregations:
    ELK, Datadog, etc.
    """

    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }

        # Merge any extra data attached to the records
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
        return json.dumps(log_obj)

def get_logger (name: str = "production-api") -> logging.Logger:
    """Create a structure JSON logger."""

    logger = logging.getLogger(name=name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

# === Metrics Collector ===

class MetricsCollector:
    """
    Collects and aggregates application metrics.

    In production, replace with Prometheus client:
        from prometheus import Counter, Histogram
    """
    def __init__ (self):
        self._requests_total = 0
        self._errors_total = 0
        self._latency_sum = 0.0
        self._tokens_input = 0
        self._tokens_output = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._latency_count = 0
        
    def record_request(
        self,
        success: bool,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        error: bool = False,
        cache_hit: bool = False,
    ):
        """
        Record a request.

        Args:
            success: Whether the request was successful
            latency_ms: Request latency in milliseconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            error: Whether the request resulted in an error
            cache_hit: Whether the request was served from cache
        """

        self._requests_total +=     1
        self._latency_sum += latency_ms
        self._latency_count += 1
        self._tokens_input += input_tokens
        self._tokens_output += output_tokens

        if error:
            self._errors_total += 1
        
        if not cache_hit:
            self._cache_misses += 1
        else:
            self._cache_hits += 1

    @property
    def summary(self) -> dict:
        """Compute summary metrics."""
        avg_latency = (
            self._latency_sum / self._latency_count
            if self._latency_count > 0 else 0.0
        )

        error_rate = (
            self._errors_total / self._requests_total
            if self._requests_total > 0 else 0.0
        )

        cache_total = self._cache_hits + self._cache_misses
        cache_hit_rate = (
            self._cache_hits / cache_total
            if cache_total > 0 else 0.0
        )

        return {
            "total_requests": self._requests_total,
            "total_errors": self._errors_total,
            "avg_latency_ms": f"{avg_latency:.2f}",
            "input_tokens": self._tokens_input,
            "output_tokens": self._tokens_output,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": f"{cache_hit_rate:.2%}",
            "error_rate": f"{error_rate:.2%}",
        }

# === Request Timer (utility) ===

class RequestTimer:
    """Context manager for timing requests."""

    def __enter__ (self):
        self.start = time.time()
        return self

    def __exit__ (self, *args):
        self.elapsed_ms = (time.time() - self.start) * 1000
        
