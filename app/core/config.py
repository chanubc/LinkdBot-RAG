from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    OPENAI_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str
    NOTION_CLIENT_ID: str
    NOTION_CLIENT_SECRET: str
    NOTION_REDIRECT_URI: str
    ENCRYPTION_KEY: str  # Fernet key
    JINA_API_KEY: str | None = None
    TELEGRAM_TEST_ID: int | None = None
    DASHBOARD_JWT_SECRET: str  # 기본값 없음 — .env 필수 설정
    DASHBOARD_URL: str = "http://localhost:8501"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
