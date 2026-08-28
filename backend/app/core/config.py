from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables / .env file.
    All secrets are sourced here; never read os.environ directly in other modules.
    """

    model_config = SettingsConfigDict(env_file=str(_ROOT_ENV), extra="ignore")

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str
    app_base_url: str

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str

    # ── Supabase (v2) ─────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # backend-only; NEVER in clients
    supabase_jwt_secret: str = ""  # fallback only; v2 verifies via JWKS RS256

    # ── Telegram linking token ────────────────────────────────────────────────
    # Secret penandatangan token SSO telegram-link (short-lived JWT) pada alur
    # /start → link. BUKAN legacy v1 — masih dipakai v2 untuk alur linking.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"

    # ── LLM — env-driven (satu gateway call_llm) ─────────────────────────────
    llm_provider: str = "auto"  # auto | openrouter | deepseek
    openrouter_api_key: str = ""
    openrouter_base_url: str
    llm_text_model: str = ""
    llm_vision_model: str = ""
    llm_text_fallback: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str

    # ── Telegram ─────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_webhook_secret: str

    # Public URL of the Node bot service (setWebhook target), supplied by env.
    bot_public_url: str

    # ── Service-to-service (bot → backend) ────────────────────────────────────
    bot_service_token: str = ""


settings = Settings()
