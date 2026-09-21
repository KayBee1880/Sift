from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    postgres_user: str = "sift"
    postgres_password: str = "sift_dev_password"
    postgres_db: str = "sift"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    # Empty locally (Docker Compose Postgres doesn't use SSL). Managed providers
    # like Neon require it — set to "require" via environment variable in a real
    # deployment, never hardcoded here, since it must stay off for local dev.
    postgres_sslmode: str = ""

    groq_api_key: str = ""
    groq_model_name: str = "openai/gpt-oss-120b"

    # Dev-only placeholder, same convention already used for postgres_password:
    # a non-secret, clearly-local default committed in the open, never meant for
    # a real deployment. A real deployment would set this from a real secret
    # store/environment variable, the same way GROQ_API_KEY is kept out of the
    # repo via .env.
    jwt_secret_key: str = "sift-dev-jwt-secret-change-before-any-real-deployment"

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # Phase 4: protects the shared free-tier Groq quota on the live public
    # deployment from being exhausted by one caller, not a guess at future
    # scale. Per-account, sliding window.
    rate_limit_max_requests: int = 10
    rate_limit_window_seconds: float = 60.0

    # Phase 4: identical (query, permission-set) requests skip a redundant
    # Groq call. In-memory, single-process — correct for this project's
    # single Render instance.
    query_cache_max_size: int = 200
    query_cache_ttl_seconds: float = 300.0

    @property
    def database_url(self) -> str:
        url = (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        if self.postgres_sslmode:
            url += f"?sslmode={self.postgres_sslmode}"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
