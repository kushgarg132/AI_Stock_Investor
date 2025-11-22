from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "AI Stock Investor"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"

    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "stock_investor_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # API Keys (Set these in your .env file)
    OPENAI_API_KEY: Optional[str] = None
    NEWS_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    FMP_API_KEY: Optional[str] = None  # Financial Modeling Prep

    # System Settings
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
