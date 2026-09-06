"""The engine seam that turns long-term orders into suggestions.

Intraday signals still execute themselves -- nobody can approve a 5-minute
breakout in time for it to still be one -- while long-term signals stop here
and wait for a person. Both halves keep the same sizing and scoring; the only
difference is who presses the button.
"""

import logging
from typing import Optional

from backend.engine.runner import Proposal

logger = logging.getLogger(__name__)

GATED_MODE = "LONGTERM"


class SuggestionSink:
    """`armed` exists for the scan path (backend/suggestions/scan.py), which
    replays months of history to warm the strategies up: signals from those
    warmup bars are history, not advice, so they are dropped rather than
    recorded. A live run leaves it armed throughout."""

    def __init__(self, store, user_id: str, run_id: Optional[str] = None, source: str = "run") -> None:
        self.store = store
        self.user_id = user_id
        self.run_id = run_id
        self.source = source
        self.armed = True

    async def __call__(self, proposal: Proposal) -> bool:
        if proposal.mode != GATED_MODE:
            return True
        if not self.armed:
            return False

        # One open idea per symbol: a daily scan re-derives the same signal
        # from the same bars, and the inbox is for deciding, not scrolling.
        if await self.store.has_pending(self.user_id, proposal.order.symbol, proposal.mode):
            return False

        suggestion = await self.store.create(
            user_id=self.user_id, proposal=proposal, source=self.source, run_id=self.run_id,
        )
        logger.info(
            "suggestion %s pending approval: %s %s x%s",
            suggestion["id"], proposal.order.side, proposal.order.symbol, proposal.order.quantity,
        )
        return False
