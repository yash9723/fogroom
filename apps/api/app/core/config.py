"""Application settings, loaded from environment variables / the repo-root `.env`."""

from functools import cached_property
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root in a source checkout (apps/api/app/core/config.py); inside the Docker image
# the tree is shallower, so fall back to the filesystem root (env vars are used there).
_PARENTS = Path(__file__).resolve().parents
REPO_ROOT = _PARENTS[4] if len(_PARENTS) > 4 else _PARENTS[-1]
_DEFAULT_SECRET = "change-me-to-a-long-random-string"  # noqa: S105 - documented dev default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://fogroom:fogroom@localhost:5432/fogroom"
    test_database_url: str = "postgresql+asyncpg://fogroom:fogroom@localhost:5432/fogroom_test"
    redis_url: str = "redis://localhost:6379/0"
    test_redis_url: str = "redis://localhost:6379/15"

    jwt_secret: str = _DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_access_expiration_minutes: int = 15
    jwt_refresh_expiration_days: int = 7

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    demo_mode: bool = False
    demo_password: str = "FogRoom!2026"

    engine_autorun: bool = True
    engine_tick_seconds: float = 1.0

    login_rate_limit: int = 10
    login_rate_window_seconds: int = 300

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"

    # Use NullPool (no connection reuse) - required when the same engine is used
    # from several event loops, e.g. in tests with Starlette's TestClient.
    db_null_pool: bool = False

    @model_validator(mode="after")
    def _check_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.jwt_secret == _DEFAULT_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a strong value in production")
            if self.demo_mode:
                raise ValueError("DEMO_MODE must be disabled in production")
        return self

    @cached_property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


settings = Settings()
