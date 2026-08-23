import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
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


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("startup", env=settings.app_env, base_url=settings.app_base_url)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """
    Liveness endpoint. Returns 200 if the backend is running.
    Used by Docker Compose health checks and uptime monitors.
    """
    return {"status": "ok", "env": settings.app_env}
