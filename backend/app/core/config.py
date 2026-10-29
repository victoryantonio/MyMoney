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

    # ── LLM — env-driven (satu gateway call_llm) ─────────────────────────────
    llm_provider: str = "auto"  # auto | openrouter | deepseek
    openrouter_api_key: str = ""
    openrouter_base_url: str
    llm_text_model: str = ""
    llm_vision_model: str = ""
    llm_text_fallback: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str


settings = Settings()
