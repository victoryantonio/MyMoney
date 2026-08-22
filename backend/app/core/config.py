from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DB_NAME: str = "mymoney"

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # LLM — GLM 5.2
    GLM_API_KEY: str
    GLM_API_BASE_URL: str = "https://open.bigmodel.cn/api/paas/v4"

    # LLM — Gemini
    GEMINI_API_KEY: str

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str

    # App
    APP_ENV: str = "development"
    RECEIPTS_DIR: str = "/app/receipts"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
