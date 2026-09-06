import sys
import os
import uvicorn

# Add project root to sys.path to allow imports from configs, mcp_tools, etc.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.auth.dependency import get_current_user
from backend.auth.refresh_store import RefreshTokenStore
from backend.auth.store import UserStore
from backend.configs.settings import settings
from backend.runs import RunStore
from backend.suggestions.store import SuggestionStore
from backend.prefs import PrefsStore
from backend import scheduler
from backend.ws import pump as ws_pump
from backend.ws import routes as ws_routes
from backend.configs.logging_config import setup_logging
from backend.database import db
from backend.instruments.master import InstrumentMaster
from backend.instruments.loader import SeedFileSource, refresh_instruments, refresh_from_kite_if_connected

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
    master = InstrumentMaster(db.db)
    await master.ensure_indexes()
    await UserStore(db.db).ensure_indexes()
    await RefreshTokenStore(db.db).ensure_indexes()
    count = await refresh_instruments(SeedFileSource(), master)
    logger.info(f"Instrument master seeded: {count} upserted.")
    kite_count = await refresh_from_kite_if_connected()
    if kite_count:
        logger.info(f"Instrument master expanded from Kite: {kite_count} upserted.")

    await SuggestionStore(db.db).ensure_indexes()
    await PrefsStore(db.db).ensure_indexes()

    # Post-close scan, sentiment refresh and suggestion expiry.
    scheduler.start(db.db, db.redis)
    # Live prices and P&L for whoever has a socket open.
    ws_pump.start(db.db)

    # An asyncio.Task cannot outlive the process that created it, so any run
    # still marked RUNNING belongs to a previous life of this container.
    runs = RunStore(db.db)
    await runs.ensure_indexes()
    orphaned = await runs.close_orphaned()
    if orphaned:
        logger.info(f"Closed {orphaned} orphaned trading run(s) from a previous process.")

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
from backend.routers import suggestions
from backend.routers import analytics
from backend.routers import broker

app.include_router(market_data.router, prefix=settings.API_PREFIX, tags=["Market Data"], dependencies=[Depends(get_current_user)])
app.include_router(watchlist.router, prefix=settings.API_PREFIX, tags=["Watchlist"], dependencies=[Depends(get_current_user)])
app.include_router(trading.router, prefix=settings.API_PREFIX, tags=["Trading"], dependencies=[Depends(get_current_user)])
app.include_router(suggestions.router, prefix=settings.API_PREFIX, tags=["Suggestions"], dependencies=[Depends(get_current_user)])
app.include_router(analytics.router, prefix=settings.API_PREFIX, tags=["Analytics"], dependencies=[Depends(get_current_user)])
app.include_router(broker.router, prefix=settings.API_PREFIX, tags=["Broker"], dependencies=[Depends(get_current_user)])

# The socket authenticates its own handshake (see backend/ws/routes.py): the
# HTTP bearer dependency cannot run on a WebSocket upgrade.
app.include_router(ws_routes.router, prefix=settings.API_PREFIX, tags=["Live"])

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
