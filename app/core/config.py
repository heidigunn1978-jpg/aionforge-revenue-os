"""Application configuration using Pydantic."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # API Configuration
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    SECRET_KEY: str = "your-secret-key-change-in-production"
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://localhost/aionforge_revenue_os"

    # Gumroad
    GUMROAD_API_KEY: str = ""
    GUMROAD_WEBHOOK_SECRET: str = ""

    # Notion
    NOTION_API_KEY: str = ""
    NOTION_DATABASE_ID: str = ""
    NOTION_VERSION: str = "2022-06-28"

    # Email Service
    EMAIL_PROVIDER: str = "sendgrid"  # sendgrid or mailgun
    EMAIL_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@aionforge.com"
    EMAIL_FROM_NAME: str = "AIONForge"

    # Stripe (optional)
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
