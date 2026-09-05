from pydantic_settings import BaseSettings
from pydantic import field_validator, ValidationInfo
from typing import Optional, List

class Settings(BaseSettings):
    # Project Info
    PROJECT_NAME: str = "AI Stock Investor"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    SERVER_PORT: int = 8001  # Port the server runs on

    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "stock_investor_db"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # API Keys (Set these in your .env file)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_API_KEYS: List[str] = []
    
    # OmniRoute (self-hosted OpenAI-compatible gateway) -- GEMINI_API_KEY(S) above
    # holds the OmniRoute gateway key, not a real Google key, when this is used.
    OMNIROUTE_BASE_URL: str = "http://omniroute:20128/v1"
    OMNIROUTE_MODEL: str = "antigravity/gemini-2.5-flash"

    FINNHUB_API_KEY: Optional[str] = None

    # Zerodha Kite Connect (Task 5) -- both None until a real app is
    # registered at developers.kite.trade; KiteSessionManager must treat
    # that as UNCONFIGURED, not crash.
    KITE_API_KEY: Optional[str] = None
    KITE_API_SECRET: Optional[str] = None

    @field_validator("GEMINI_API_KEYS", mode="before")
    @classmethod
    def assemble_gemini_keys(cls, v: Optional[List[str]], info: ValidationInfo) -> List[str]:
        if isinstance(v, list) and v:
            return v
        # Fallback to splitting the single key if it contains commas, or just using it
        values = info.data.get("GEMINI_API_KEY")
        if values:
            return [k.strip() for k in values.split(",") if k.strip()]
        return []

    # System Settings
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
