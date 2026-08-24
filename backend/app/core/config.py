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

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # ── DeepSeek ──────────────────────────────────────────────────────────────
    deepseek_api_key: str = ""
    # /v1 is required: the working client config calls https://api.deepseek.com/v1/chat/completions
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # ── Telegram ─────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_webhook_secret: str

    # ── Storage ───────────────────────────────────────────────────────────────
    receipts_dir: str = "/app/receipts"


settings = Settings()
