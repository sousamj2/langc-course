"""
Centralized Configuration
Uses pydantic-settings for validated enviroment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from pydantic import Field, AliasChoices

class Settings(BaseSettings):
    """
    Application configuration settings.
    Enviroment variables will override defaults from .env file.
    """

    # config_key: config_type = default_value # comment to understand the config key

    # AWS Configuration
    aws_api_key: str = Field(validation_alias=AliasChoices("AWS_BEARER_TOKEN_BEDROCK", "AWS_API_KEY")) # AWS api key
    aws_region: str = Field(validation_alias=AliasChoices("AWS_REGION", "AWS_REGION")) # AWS region
    aws_model: str = Field(validation_alias=AliasChoices("AWS_MODEL", "AWS_MODEL")) # AWS model
    

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
    langsmith_tracing_v2: bool = Field(
        default=True, 
        validation_alias=AliasChoices("LANGCHAIN_TRACING", "LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "LANGSMITH_TRACING_V2")
    ) # Enable LangSmith tracing
    langsmith_api_key: str = Field(
        validation_alias=AliasChoices("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY")
    )  # API key for the LangSmith API
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com", 
        validation_alias=AliasChoices("LANGCHAIN_ENDPOINT", "LANGSMITH_ENDPOINT")
    ) # LangSmith endpoint
    langsmith_project_name: str = Field(
        default="production-api", 
        validation_alias=AliasChoices("LANGCHAIN_PROJECT", "LANGSMITH_PROJECT")
    ) # LangSmith project name

    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    rate_limit: str = "15/minute" # Rate limit for the application
    cache_ttl_seconds: int = 300 # Cache time-to-live in seconds
    max_retries: int = 4 # primary + fallback + primary after 10 second delay + fallback.

    model_config = {"env_file": ".env", "extra": "ignore"}

    def model_post_init(self, __context):
        import os
        # Export settings to os.environ so they are picked up by LangChain/LangSmith SDKs
        # Only set them if they aren't already explicitly set in os.environ (e.g. overridden by tests)
        tracing_str = "true" if self.langsmith_tracing_v2 else "false"
        
        if "LANGCHAIN_TRACING_V2" not in os.environ:
            os.environ["LANGCHAIN_TRACING_V2"] = tracing_str
        if "LANGSMITH_TRACING_V2" not in os.environ:
            os.environ["LANGSMITH_TRACING_V2"] = tracing_str
        if "LANGCHAIN_TRACING" not in os.environ:
            os.environ["LANGCHAIN_TRACING"] = tracing_str
        if "LANGSMITH_TRACING" not in os.environ:
            os.environ["LANGSMITH_TRACING"] = tracing_str

        if self.langsmith_api_key:
            if "LANGCHAIN_API_KEY" not in os.environ:
                os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            if "LANGSMITH_API_KEY" not in os.environ:
                os.environ["LANGSMITH_API_KEY"] = self.langsmith_api_key

        if self.langsmith_endpoint:
            if "LANGCHAIN_ENDPOINT" not in os.environ:
                os.environ["LANGCHAIN_ENDPOINT"] = self.langsmith_endpoint
            if "LANGSMITH_ENDPOINT" not in os.environ:
                os.environ["LANGSMITH_ENDPOINT"] = self.langsmith_endpoint

        if self.langsmith_project_name:
            if "LANGCHAIN_PROJECT" not in os.environ:
                os.environ["LANGCHAIN_PROJECT"] = self.langsmith_project_name
            if "LANGSMITH_PROJECT" not in os.environ:
                os.environ["LANGSMITH_PROJECT"] = self.langsmith_project_name

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

