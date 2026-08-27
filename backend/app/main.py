"""
FastAPI application entrypoint.

Startup order:
  1. structlog configured
  2. FastAPI app created with CORS middleware
  3. All routers included
  4. /health liveness endpoint registered
"""

from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter

STATIC_DIR = Path(__file__).resolve().parent / "static"

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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware order: last added = outermost. CORS stays outermost, rate
# limiting runs just inside it.
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [settings.app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.api import (  # noqa: E402
    accounts,
    categories,
    receipts,
    reports,
    telegram_linking,
    telegram_webhook,
    transactions,
)

app.include_router(telegram_webhook.router)
app.include_router(telegram_linking.router)
app.include_router(categories.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(receipts.router)
app.include_router(reports.router)

# ── Static files (brand logo used by the Telegram linking pages) ─────────────
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


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
