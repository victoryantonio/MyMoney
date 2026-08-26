from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All secrets are sourced here; never read os.environ directly in other modules.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_base_url: str = "http://localhost:8000"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str

    # ── Supabase (v2) ─────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # backend-only; NEVER in clients
    supabase_jwt_secret: str = ""  # fallback only; v2 verifies via JWKS RS256
    supabase_storage_bucket_receipts: str = "receipts"

    # ── JWT (v1 legacy — Supabase Auth menggantikan di Fase 1) ────────────────
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # ── LLM — env-driven (satu gateway call_llm) ─────────────────────────────
    llm_provider: str = "auto"  # auto | openrouter | deepseek
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_text_model: str = ""
    llm_vision_model: str = ""
    llm_text_fallback: str = ""
    deepseek_api_key: str = ""
    # /v1 is required: the working client config calls https://api.deepseek.com/v1/chat/completions
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ── Telegram ─────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_webhook_secret: str

    # ── Service-to-service (bot → backend) ────────────────────────────────────
    bot_service_token: str = ""

    # ── Storage ───────────────────────────────────────────────────────────────
    receipts_dir: str = "/app/receipts"


settings = Settings()
