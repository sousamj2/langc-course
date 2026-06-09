"""
Centralized Configuration
Uses pydantic-settings for validated enviroment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application configuration settings.
    Enviroment variables will override defaults from .env file.
    """

    # config_key: config_type = default_value # comment to understand the config key

    # LLM Configurations
    gemini_api_key: str # API key for the Gemini API
    live_model: str = "gemini-3.1-flash-live-preview" # bi-directional streaming using a websocket connection. Up to 65k TPM with unlimitted RPM and RPD.
    primary_model: str = "gemini-3.1-flash-lite" # Best model in the free tier with 15 RPM, 250k TPM and 500 RPD.
    # primary_model: str = "gemma-4-31b-it" # Temporary setting primary to gemma4.
    secondary_model: str = "gemma-4-31b-it" # Best open model with Unlimitted RPM and TPM but limited to 1500 RPD.
    fallback_model: str = "gemma-4-26b-a4b-it" # fallback open model with Unlimitted RPM and TPM but limited to 1500 RPD.
    temperature: float = 0.2
    max_tokens: int = 1024
    timeout: int = 30
    streaming: bool = True
    verbose: bool = True
    
    # LangSmith
    langsmith_tracing_v2: bool = True # Enable LangSmith tracing
    langsmith_api_key: str  # API key for the LangSmith API
    langsmith_endpoint: str = "https://api.smith.langchain.com" # LangSmith endpoint
    langsmith_project_name: str = "production-api" # LangSmith project name

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "15/minute" # Rate limit for the application
    cache_ttl_seconds: int = 300 # Cache time-to-live in seconds
    max_retries: int = 4 # primary + fallback + primary after 10 second delay + fallback.

    model_config = {"env_file": ".env", "extra": "ignore"}

    # Property functions are not enviroment variables but derived values (not cached)
    # This means they are calculated every time they are called

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
    
    
# lru_cache caches the result of a function call
# This means that the function will only be called once
# The cache will be cleared when the application restarts
@lru_cache
def get_settings() -> Settings:
    """Cache settings instance - load once, reused everywhere."""
    return Settings()

