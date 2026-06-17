FROM python:3.12-slim

WORKDIR /app

# Install uv (fast python package manager)
RUN pip install uv

# Create a non-root user for security
RUN useradd --create-home appuser && chown -R appuser:appuser /app

# Copy dependencies files first (Docker layer caching)
COPY --chown=appuser:appuser pyproject.toml .
COPY --chown=appuser:appuser uv.lock* .

USER appuser

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY --chown=appuser:appuser app/ app/

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application with uvicorn
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

