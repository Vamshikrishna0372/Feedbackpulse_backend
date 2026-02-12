from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal

class Settings(BaseSettings):
    """
    Application configuration using Pydantic Settings.
    Reads environment variables from .env file automatically.
    """
    PROJECT_NAME: str = "FeedbackPulse Backend"
    MONGODB_URI: str
    DB_NAME: str = "feedbackpulse"
    
    # Security (No defaults for sensitive values in production)
    JWT_SECRET: str  # Must be set in environment
    JWT_EXPIRE_MINUTES: int = 30
    ALGORITHM: str = "HS256"
    
    # Environment
    ENVIRONMENT: Literal["development", "production"] = "development"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"] # Defaults for local dev

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True # Pydantic v2 usually defaults to case insensitive, but env vars are case sensitive on Linux.
        # But 'case_sensitive=True' means model fields must match env var case? No, the other way.
        # To make it easy, allow case insensitive matching (which is default).
        # But wait, env vars like JWT_SECRET map to jwt_secret if case_sensitive=False?
        # Actually pydantic-settings v2 matches case-insensitive by default.
        # Let's verify behavior. If I name fields UPPERCASE, pydantic might expect env var UPPERCASE anyway.
        # Let's rely on default behavior or be explicit.
    )

from dotenv import load_dotenv
load_dotenv()

# Instantiate settings at module level for easy import
settings = Settings()
