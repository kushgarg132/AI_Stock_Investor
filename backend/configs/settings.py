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

    # OmniRoute (self-hosted OpenAI-compatible gateway) -- the only LLM
    # provider this app uses. OMNIROUTE_API_KEY(S) holds the gateway key
    # issued from the OmniRoute dashboard's Endpoints page, not a Google key.
    OMNIROUTE_API_KEY: Optional[str] = None
    OMNIROUTE_API_KEYS: List[str] = []
    OMNIROUTE_BASE_URL: str = "http://omniroute:20128/v1"
    OMNIROUTE_MODEL: str = "antigravity/gemini-2.5-flash"

    FINNHUB_API_KEY: Optional[str] = None

    # Zerodha Kite Connect (Task 5) -- both None until a real app is
    # registered at developers.kite.trade; KiteSessionManager must treat
    # that as UNCONFIGURED, not crash.
    KITE_API_KEY: Optional[str] = None
    KITE_API_SECRET: Optional[str] = None

    # Google Sign-In (ID-token verification only -- no client secret, no
    # redirect URI needed for this flow).
    GOOGLE_CLIENT_ID: Optional[str] = None

    # Session JWT (bearer token, not a cookie -- see auth design spec).
    JWT_SECRET: str = "change-me-in-production"
    SESSION_MAX_AGE_SECONDS: int = 604800  # 7 days

    # Explicit CORS allowlist -- replaces allow_origins=["*"], which is an
    # invalid combination with allow_credentials=True for real credentialed
    # cross-origin requests.
    CORS_ALLOWED_ORIGINS: List[str] = ["http://localhost:5173"]

    @field_validator("CORS_ALLOWED_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("OMNIROUTE_API_KEYS", mode="before")
    @classmethod
    def assemble_omniroute_keys(cls, v: Optional[List[str]], info: ValidationInfo) -> List[str]:
        if isinstance(v, list) and v:
            return v
        # Fallback to splitting the single key if it contains commas, or just using it
        values = info.data.get("OMNIROUTE_API_KEY")
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
