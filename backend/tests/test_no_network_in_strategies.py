"""Grep-based regression guard: no file under backend/strategies/ may reach
for yfinance directly -- strategies only see Bars handed to them by
ctx.history()/on_bar(), never fetch their own data (see test_no_datetime_now.py
for the sibling datetime.now()/utcnow() guard).
"""

import re
from pathlib import Path

FORBIDDEN = re.compile(r"\byf\.")


def test_no_yfinance_calls_in_strategies():
    repo_root = Path(__file__).resolve().parents[2]
    strategies_dir = repo_root / "backend" / "strategies"
    assert strategies_dir.is_dir()

    offenders = [
        str(path.relative_to(repo_root))
        for path in strategies_dir.rglob("*.py")
        if FORBIDDEN.search(path.read_text())
    ]
    assert not offenders, f"yfinance usage found in: {offenders}"
