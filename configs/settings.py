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
    GEMINI_API_KEY: Optional[str] = "AIzaSyA2YUFiama2Wumq07Ncc3hISNP87paVvyk"
    NEWS_API_KEY: Optional[str] = "60c8b36b26414ee8b4e52f61868fe4b1"
    ALPHA_VANTAGE_API_KEY: Optional[str] = "HY3EJMJIW5AUMKKD"
    FMP_API_KEY: Optional[str] = "bCsvD4k7rryfJW0Ds9iy2JIlHj9WId0P"

    # System Settings
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
