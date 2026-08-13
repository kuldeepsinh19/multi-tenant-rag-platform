from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Environments treated as non-production for the purpose of relaxing startup checks
# (weak-secret and provider-key enforcement) and exposing interactive API docs.
_NON_PROD_ENVS = {"development", "dev", "local", "test", "testing", "ci"}

# JWT secrets that must never reach a production deployment — the shipped placeholder and
# obvious weak values. A production start with any of these (or a too-short secret) fails
# fast rather than signing forgeable tokens with a guessable key.
_WEAK_JWT_SECRETS = {
    "",
    "change-me-to-a-long-random-value",
    "changeme",
    "change-me",
    "secret",
    "your-secret-key",
}
_MIN_JWT_SECRET_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"

    # -- Postgres / Redis --
    database_url: str = "postgresql+asyncpg://platform:platform@postgres:5432/platform"
    redis_url: str = "redis://redis:6379/0"

    # -- Auth --
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 60

    # -- CORS --
    dashboard_origins: list[str] = ["http://localhost:5173"]

    # -- LLM / embedding provider selection (see src/llm/registry.py) --
    # Swapping providers is an env change only; no code moves.
    llm_provider: str = "groq"
    llm_fallback_provider: str = "gemini"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_fallback_model: str = "gemini-2.0-flash"
    groq_api_key: str = ""
    gemini_api_key: str = ""

    embed_provider: str = "gemini"
    embed_model: str = "gemini-embedding-001"
    # Pinned because the pgvector column dimension depends on it — changing
    # the embedding model/dim requires a migration + full re-index.
    embed_dim: int = 768

    # -- Rate limiting / cost control --
    rate_limit_requests_per_minute: int = 30
    per_business_daily_token_budget: int = 200_000

    # -- Retrieval --
    retrieval_top_k_candidates: int = 20
    retrieval_top_k_final: int = 5
    retrieval_min_score: float = 0.35

    # -- Agent --
    agent_max_retries: int = 2

    # -- Observability / tracing (Langfuse) --
    # All optional and default to empty: when unset, tracing is a strict NO-OP and never
    # raises. Tracing is fail-open (an outage must not break a request) — see
    # src/observability/tracing.py.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    @property
    def is_production(self) -> bool:
        return self.env.strip().lower() not in _NON_PROD_ENVS

    @property
    def docs_enabled(self) -> bool:
        """Interactive docs (/docs, /redoc, /openapi.json) are dev-only — publishing the
        full API surface anonymously in production is needless exposure."""
        return not self.is_production

    def _api_key_for(self, provider: str) -> str:
        return {"groq": self.groq_api_key, "gemini": self.gemini_api_key}.get(provider, "")

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Fail fast on an insecure production configuration. Non-production envs skip
        these checks so local/test setups stay frictionless."""
        if not self.is_production:
            return self
        if self.jwt_secret in _WEAK_JWT_SECRETS or len(self.jwt_secret) < _MIN_JWT_SECRET_LEN:
            raise ValueError(
                "JWT_SECRET is missing, a known placeholder, or too short for production; "
                f"set a random value of at least {_MIN_JWT_SECRET_LEN} characters "
                '(e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).'
            )
        # Every selected provider (chat, fallback, embeddings) must have its API key present,
        # so a misconfigured prod deploy fails at boot instead of on the first request.
        required = {
            "chat": self.llm_provider,
            "fallback": self.llm_fallback_provider,
            "embeddings": self.embed_provider,
        }
        missing = [
            f"{role} provider '{prov}'"
            for role, prov in required.items()
            if not self._api_key_for(prov)
        ]
        if missing:
            raise ValueError(
                "Missing API key(s) for selected provider(s) in production: "
                + ", ".join(missing)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
