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
    """Reads the bundled NSE equity fixture. Stand-in for the Kite instruments
    dump (`GET /instruments`) until Task 5 adds a KiteInstrumentSource
    implementing this same protocol."""

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
