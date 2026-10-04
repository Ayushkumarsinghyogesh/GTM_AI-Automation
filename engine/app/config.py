"""Environment settings. Lazy: import time pe env nahi padhta (tests easy)."""
from functools import lru_cache
from pathlib import Path
from functools import lru_cacheexit


from pydantic_settings import BaseSettings, SettingsConfigDict
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", case_sensitive=False)

    engine_api_key: str
    supabase_url: str
    supabase_service_role_key: str

    anthropic_api_key: str = ""
    claude_model_write: str = "claude-sonnet-5-5"
    claude_model_classify: str = "claude-haiku-4-5-20251001"

    heyreach_api_key: str = ""
    heyreach_base_url: str = "https://api.heyreach.io/api/public"
    heyreach_default_campaign_id: int | None = None
    heyreach_sender_account_id: int | None = None

    max_launch_per_run: int = 25
    max_event_attempts: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
