from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_app_id: Optional[str] = None
    github_app_private_key_path: Optional[str] = None
    github_webhook_secret: str = Field(default="", repr=False)
    github_installation_id: Optional[str] = None
    github_api_url: str = "https://api.github.com"

    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = Field(default=None, repr=False)
    llm_model: Optional[str] = None
    llm_base_url: str = "https://api.deepseek.com"

    database_url: str = "sqlite:///./review_agent.db"
    review_draft_pr: bool = False
    max_diff_lines: int = 3000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
