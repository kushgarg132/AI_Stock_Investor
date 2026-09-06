import json
import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from backend.instruments.master import InstrumentMaster
from backend.instruments.models import Instrument

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).parent / "seed_nse_equity.json"


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
