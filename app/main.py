import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)

from app.api.v1.endpoints import auth, search, webhook


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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
