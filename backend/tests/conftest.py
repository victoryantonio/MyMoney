"""
conftest.py — pytest fixtures and env setup for unit tests.
Sets required env vars so Settings() doesn't fail during import.
"""
import os
import pytest

# Set minimal env vars required by pydantic-settings before any app import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_unit_tests_only_not_real")
os.environ.setdefault("GLM_API_KEY", "test_glm_key")
os.environ.setdefault("GEMINI_API_KEY", "test_gemini_key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_telegram_token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test_webhook_secret")
os.environ.setdefault("APP_ENV", "test")
