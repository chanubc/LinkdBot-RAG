import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from app.api.v1.endpoints import auth, search, webhook
from app.api.dependencies.auth_di import get_telegram_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    telegram_repo = get_telegram_client()
    success = await telegram_repo.register_commands()
    if success:
        logger.info("✅ Telegram bot commands registered successfully")
    else:
        logger.warning("⚠️ Failed to register Telegram bot commands")

    yield

    # Shutdown (if needed)


app = FastAPI(
    title="LinkdBot-RAG",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(webhook.router, prefix="/api/v1/webhook", tags=["webhook"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
