import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.api import auth, transactions, accounts, categories
from app.api import telegram_webhook, reports
from app.api import receipts

configure_logging()
logger = structlog.get_logger(__name__)

app = FastAPI(
    title="MyMoney API",
    description="Personal finance tracker — Telegram bot + Android app backend.",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register all routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(receipts.router, prefix="/api/v1")
app.include_router(telegram_webhook.router)  # no /api/v1 prefix — Telegram calls /webhook/telegram


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness probe — confirms the backend is running."""
    return {"status": "ok", "version": "0.1.0"}


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("backend_started", env=settings.APP_ENV)
