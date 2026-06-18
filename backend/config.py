from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_name: str = "English Reader"
    debug: bool = False
    secret_key: str = "change-this-in-production"

    # Database
    database_url: str = "sqlite+aiosqlite:///./english_reader.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 86400

    # LLM
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_provider: str = "anthropic"  # "openai" or "anthropic"

    # RSS
    rss_feeds: str = (
        "http://feeds.bbci.co.uk/news/world/rss.xml,"
        "https://feeds.npr.org/1001/rss.xml"
    )

    @property
    def rss_feed_list(self) -> list[str]:
        return [f.strip() for f in self.rss_feeds.split(",") if f.strip()]

    # JWT
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080


@lru_cache
def get_settings() -> Settings:
    return Settings()
