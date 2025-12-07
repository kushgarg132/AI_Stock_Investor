import sys
import os
import uvicorn

# Add project root to sys.path to allow imports from configs, mcp_tools, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from configs.settings import settings
from configs.logging_config import setup_logging
from backend.database import db

# Setup Logging
logger = setup_logging()
from mcp_tools import (
    news_fetcher,
    news_sentiment,
    event_classifier,
    price_history_fetcher,
    support_resistance_detector,
    trend_detector,
    volume_spike_detector,
    risk_rules_tool,
    stock_info_fetcher,
    goals_api,
    stock_scanner
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Events
@app.on_event("startup")
async def startup_db_client():
    logger.info("Starting up AI Stock Investor API...")
    await db.connect_to_database()
    logger.info("Database connected.")

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down AI Stock Investor API...")
    await db.close_database_connection()
    logger.info("Database disconnected.")

# Include Routers
app.include_router(news_fetcher.router, prefix=settings.API_PREFIX, tags=["News"])
app.include_router(news_sentiment.router, prefix=settings.API_PREFIX, tags=["News"])
app.include_router(event_classifier.router, prefix=settings.API_PREFIX, tags=["Events"])
app.include_router(price_history_fetcher.router, prefix=settings.API_PREFIX, tags=["Market Data"])
app.include_router(support_resistance_detector.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"])
app.include_router(trend_detector.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"])
app.include_router(volume_spike_detector.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"])
app.include_router(risk_rules_tool.router, prefix=settings.API_PREFIX, tags=["Risk"])
app.include_router(stock_info_fetcher.router, prefix=settings.API_PREFIX, tags=["Market Data"])
app.include_router(goals_api.router, prefix=settings.API_PREFIX, tags=["Goals"])
app.include_router(stock_scanner.router, prefix=settings.API_PREFIX, tags=["Scanner"])

# Agents Router
from backend.routers import agents
from backend.routers import chat

app.include_router(agents.router, prefix=f"{settings.API_PREFIX}/agents", tags=["Agents"])
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["Chat"])

from backend.routers import market_data
app.include_router(market_data.router, prefix=settings.API_PREFIX, tags=["Market Data"])

@app.get("/")
async def root():
    return {"message": "AI Stock Investor API is running"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=settings.SERVER_PORT, reload=True)
