"""
FastAPI application entrypoint.

Startup order:
  1. structlog configured
  2. FastAPI app created with CORS middleware
  3. All routers included
  4. /health liveness endpoint registered
"""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

app = FastAPI(
    title="MyMoney API",
    description="Personal finance tracking backend — REST API for Android app and Telegram bot.",
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [settings.app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.api import auth, categories, accounts, transactions, telegram_linking, telegram_webhook  # noqa: E402

app.include_router(auth.router)
app.include_router(telegram_linking.router)
app.include_router(telegram_webhook.router)
app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(transactions.router)


# ── Lifecycle ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    logger.info("startup", env=settings.app_env, base_url=settings.app_base_url)


# ── System endpoints ───────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Liveness endpoint. Returns 200 if the backend is running.
    Used by Docker Compose health checks and uptime monitors.
    """
    return {"status": "ok", "env": settings.app_env}
