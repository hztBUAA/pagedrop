from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "PageDrop"
    app_base_url: str = "http://localhost:5173"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # Database. Defaults to a local SQLite file so the app boots without Postgres;
    # production must set DATABASE_URL to a PostgreSQL DSN.
    database_url: str = "sqlite:///./pagedrop.db"

    # Security
    jwt_secret: str = "dev-insecure-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days
    token_pepper: str = "dev-insecure-token-pepper-change-me"
    auth_cookie_name: str = "pd_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # CORS — comma-separated list
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
