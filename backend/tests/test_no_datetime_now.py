"""Grep-based regression guard: no engine/core/strategy code may call
datetime.now()/utcnow() directly -- everything must go through Clock.now()
so backtests stay reproducible and paper/live trading stay swappable.
"""

import re
from pathlib import Path

FORBIDDEN = re.compile(r"datetime\.(now|utcnow)\(")


def test_no_direct_datetime_now_calls():
    repo_root = Path(__file__).resolve().parents[2]
    dirs = [repo_root / "backend" / "engine", repo_root / "backend" / "core"]

    strategies_dir = repo_root / "backend" / "strategies"
    if strategies_dir.is_dir():
        dirs.append(strategies_dir)

    offenders = []
    for directory in dirs:
        for path in directory.rglob("*.py"):
            if FORBIDDEN.search(path.read_text()):
                offenders.append(str(path.relative_to(repo_root)))

    assert not offenders, f"direct datetime.now()/utcnow() found in: {offenders}"
