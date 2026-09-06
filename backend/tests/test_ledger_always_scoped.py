"""Grep-based regression guard: no LedgerStore may be constructed without an
explicit user_id.

The ledger collections are shared by every account, so an unscoped store
silently reads and writes another user's book. The constructor already
requires the argument positionally-or-by-keyword; this catches the case where
someone passes it positionally as `LedgerStore(db, some_db_handle)` or
reintroduces a default.
"""

import re
from pathlib import Path

CONSTRUCTION = re.compile(r"LedgerStore\(([^)]*)\)")


def test_every_ledger_store_construction_names_a_user():
    repo_root = Path(__file__).resolve().parents[2]
    offenders = []

    for path in (repo_root / "backend").rglob("*.py"):
        if path == Path(__file__).resolve():
            continue  # this file names the forbidden shapes on purpose
        for match in CONSTRUCTION.finditer(path.read_text()):
            args = match.group(1)
            if not args.strip():
                continue  # `LedgerStore()` won't import, let Python complain
            if "user_id=" not in args:
                offenders.append(f"{path.relative_to(repo_root)}: LedgerStore({args})")

    assert not offenders, f"LedgerStore constructed without user_id=: {offenders}"
