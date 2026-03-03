from pydantic import model_validator
from pydantic_settings import BaseSettings

_DEV_SECRET = "dev-insecure-dashboard-secret"


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
    ENV: str = "development"  # "production" in prod .env
    DASHBOARD_JWT_SECRET: str = _DEV_SECRET
    DASHBOARD_URL: str = "http://localhost:8501"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _check_secret_in_prod(self) -> "Settings":
        if self.ENV == "production" and self.DASHBOARD_JWT_SECRET == _DEV_SECRET:
            raise ValueError(
                "DASHBOARD_JWT_SECRET must be explicitly set in production. "
                "Set ENV=production in .env only after configuring a strong secret."
            )
        return self


settings = Settings()
