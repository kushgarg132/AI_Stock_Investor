import sys
import os
import uvicorn

# Add project root to sys.path to allow imports from configs, mcp_tools, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.auth.dependency import get_current_user
from backend.configs.settings import settings
from backend.configs.logging_config import setup_logging
from backend.database import db
from backend.instruments.master import InstrumentMaster
from backend.instruments.loader import SeedFileSource, refresh_instruments

# Setup Logging
logger = setup_logging()
from backend.components.analyst import news, sentiment, events
from backend.components.quant import price, trend, support, volume, strategies
from backend.components.risk import risk
from backend.components.master import stock_info
from backend.mcp_tools import stock_scanner


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API for AI Stock Investor Platform",
    version=settings.VERSION,
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers import auth as auth_router
app.include_router(auth_router.router, prefix=settings.API_PREFIX, tags=["Auth"])

# Database Events
@app.on_event("startup")
async def startup_db_client():
    logger.info("Starting up AI Stock Investor API...")
    await db.connect_to_database()
    logger.info("Database connected.")
    count = await refresh_instruments(SeedFileSource(), InstrumentMaster(db.db))
    logger.info(f"Instrument master seeded: {count} upserted.")

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down AI Stock Investor API...")
    await db.close_database_connection()
    logger.info("Database disconnected.")

# Include Routers
app.include_router(news.router, prefix=settings.API_PREFIX, tags=["News"], dependencies=[Depends(get_current_user)])
app.include_router(sentiment.router, prefix=settings.API_PREFIX, tags=["News"], dependencies=[Depends(get_current_user)])
app.include_router(events.router, prefix=settings.API_PREFIX, tags=["Events"], dependencies=[Depends(get_current_user)])
app.include_router(price.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(support.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(trend.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(volume.router, prefix=settings.API_PREFIX, tags=["Technical Analysis"], dependencies=[Depends(get_current_user)])
app.include_router(risk.router, prefix=settings.API_PREFIX, tags=["Risk"], dependencies=[Depends(get_current_user)])
app.include_router(stock_info.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(stock_scanner.router, prefix=settings.API_PREFIX, tags=["Scanner"], dependencies=[Depends(get_current_user)])

# Agents Router
from backend.routers import agents
from backend.routers import chat

app.include_router(agents.router, prefix=f"{settings.API_PREFIX}/agents", tags=["Agents"], dependencies=[Depends(get_current_user)])
app.include_router(chat.router, prefix=f"{settings.API_PREFIX}/chat", tags=["Chat"], dependencies=[Depends(get_current_user)])

from backend.routers import settings as settings_router
app.include_router(settings_router.router, prefix=settings.API_PREFIX, tags=["Settings"], dependencies=[Depends(get_current_user)])

from backend.routers import market_data
from backend.routers import watchlist
from backend.routers import trading

app.include_router(market_data.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(watchlist.router, prefix=settings.API_PREFIX, tags=["Watchlist"], dependencies=[Depends(get_current_user)])
app.include_router(trading.router, prefix=settings.API_PREFIX, tags=["Trading"], dependencies=[Depends(get_current_user)])

@app.get("/docs", include_in_schema=False)
async def redirect_docs():
    return RedirectResponse(url=f"{settings.API_PREFIX}/docs")

@app.get("/redoc", include_in_schema=False)
async def redirect_redoc():
    return RedirectResponse(url=f"{settings.API_PREFIX}/redoc")

@app.head("/")
@app.get("/")
async def root():
    return {"message": "AI Stock Investor API is running"}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=settings.SERVER_PORT, reload=True)
