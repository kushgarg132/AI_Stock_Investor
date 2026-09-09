"""Shared 'expires at a fixed clock time in IST' math. Kite tokens die at
~06:00 IST (see backend/auth/kite_session.py:next_6am_ist, kept separate to
avoid touching that already-tested module); Upstox tokens die at 3:30 AM IST
the following day; Angel One sessions die at midnight IST. Different hour,
same shape -- generalized here rather than copied a third time.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

_IST = ZoneInfo("Asia/Kolkata")


def next_fixed_time_ist(now_utc: datetime, hour: int, minute: int = 0) -> datetime:
    """Returns the next instant, strictly after now_utc, at which the clock
    in IST reads hour:minute -- as a UTC datetime (for a Redis TTL, which
    only understands seconds)."""
    now_ist = now_utc.astimezone(_IST)
    candidate_ist = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now_ist >= candidate_ist:
        candidate_ist += timedelta(days=1)
    return candidate_ist.astimezone(timezone.utc)


def ttl_seconds_until(now_utc: datetime, hour: int, minute: int = 0) -> int:
    return max(1, int((next_fixed_time_ist(now_utc, hour, minute) - now_utc).total_seconds()))
