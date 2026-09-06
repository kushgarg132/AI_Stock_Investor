import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).parent / "seed_nse_equity.json"

# NSE/BSE's equity lists change slowly (new listings, not intraday) -- no
# reason to re-fetch and re-upsert ~7,500 rows (measured: over a minute,
# dominated by round trips to the remote Mongo, even when nothing changed)
# on every single backend restart. Also just good manners toward two
# undocumented, non-API endpoints (see free_source.py's docstring).
_FREE_SOURCE_REFRESH_INTERVAL = timedelta(hours=20)
_FREE_SOURCE_META_ID = "free_source_refresh"


@runtime_checkable
class InstrumentSource(Protocol):
    async def fetch(self) -> list[Instrument]: ...


class SeedFileSource:
    """Reads the bundled NSE equity fixture -- a small (~130 large-cap) floor
    so the app never starts with zero instruments. Task 5's KiteInstrumentSource
    (see refresh_from_kite_if_connected below) is the real, ~thousands-of-symbols
    universe; this is what search/resolution falls back to whenever Kite isn't
    connected."""

    def __init__(self, path: Path = SEED_FILE):
        self.path = path

    async def fetch(self) -> list[Instrument]:
        rows = json.loads(self.path.read_text())
        return [Instrument(**row) for row in rows]


async def refresh_instruments(source: InstrumentSource, master: InstrumentMaster) -> int:
    """Fetches from `source` and upserts into `master`. Idempotent: re-running
    with unchanged data upserts zero new/changed documents."""
    instruments = await source.fetch()
    count = await master.upsert_many(instruments)
    logger.info(f"Refreshed instrument master: {count} instruments upserted (of {len(instruments)} fetched)")
    return count


async def refresh_from_free_public_sources(master: InstrumentMaster) -> int:
    """Best-effort: NSE's and BSE's own public equity-list downloads
    (backend/instruments/free_source.py) as a free stopgap for the
    ~130-symbol seed file, until this deployment has a paid, connected Kite
    session (see refresh_from_kite_if_connected below -- which, when it does
    run, overwrites these rows with real Kite instrument_tokens for the same
    symbols). Each exchange is independent and swallows its own failure --
    NSE and BSE both rate-limit/block non-browser traffic sometimes, and one
    being unreachable shouldn't cost the other. Skips entirely (see
    _FREE_SOURCE_REFRESH_INTERVAL) if it already ran recently."""
    meta = master.collection.database["instrument_meta"]
    marker = await meta.find_one({"_id": _FREE_SOURCE_META_ID})
    if marker:
        # Motor/pymongo hand back naive UTC datetimes by default (no
        # tz_aware=True on this client) regardless of what was stored.
        last_refreshed_at = marker["last_refreshed_at"].replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - last_refreshed_at
        if age < _FREE_SOURCE_REFRESH_INTERVAL:
            logger.info(f"Free NSE/BSE instrument refresh skipped -- last ran {age} ago.")
            return 0

    from backend.instruments.free_source import BseEquityListSource, NseEquityListSource

    total = 0
    for label, source in (("NSE", NseEquityListSource()), ("BSE", BseEquityListSource())):
        try:
            total += await refresh_instruments(source, master)
        except Exception as e:
            logger.warning(f"{label} free instrument list refresh skipped: {e}")

    await meta.update_one(
        {"_id": _FREE_SOURCE_META_ID},
        {"$set": {"last_refreshed_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return total


async def refresh_from_kite_if_connected() -> int:
    """Best-effort: when a live Kite session is connected, pulls Kite's real
    NSE+BSE instrument dump (thousands of symbols, e.g. small/mid-caps like
    Mishtann Foods that the bundled seed file never had) into the instrument
    master. A no-op (returns 0) when Kite isn't configured, the daily session
    has expired, or the database isn't reachable -- the seed file stays as
    the floor either way, this only adds. Builds its own dependencies (rather
    than taking a `master`/session) so every failure mode is caught here,
    since both of this function's callers (startup, and the Kite connect
    callback) must never fail because of it."""
    from kiteconnect import KiteConnect

    from backend.auth.kite_session import KiteSessionManager, KiteSessionState
    from backend.configs.settings import settings
    from backend.database import db
    from backend.instruments.kite_source import KiteInstrumentSource

    try:
        session = KiteSessionManager(settings.KITE_API_KEY, settings.KITE_API_SECRET, db.redis)
        if await session.state() != KiteSessionState.ACTIVE:
            return 0

        access_token = await session.get_access_token()
        source = KiteInstrumentSource(
            lambda: KiteConnect(api_key=settings.KITE_API_KEY, access_token=access_token),
            exchanges=("NSE", "BSE"),
        )
        return await refresh_instruments(source, InstrumentMaster(db.db))
    except Exception as e:
        logger.warning(f"Kite instrument refresh skipped: {e}")
        return 0
