"""Core/satellite capital split. Deliberately simple -- equal-weight both
sleeves, no mean-variance optimizer or risk parity; that's explicitly out of
scope for this task and the plan. Pure function, no I/O.
"""


def allocate_core_satellite(
    total_capital: float,
    core_symbols: list[str],
    satellite_symbols: list[str],
    core_weight: float = 0.7,
) -> dict[str, float]:
    """Splits `total_capital` core_weight/(1 - core_weight) between an
    equal-weighted core sleeve (index ETFs, e.g. NIFTYBEES) and an
    equal-weighted satellite sleeve (the quality-screened active picks).

    An empty satellite list puts 100% of capital in the core sleeve (nothing
    to allocate to a satellite that doesn't exist); symmetrically, an empty
    core list puts 100% into satellite. Both lists empty raises ValueError --
    there's nothing to allocate to and returning `{}` would silently drop
    capital rather than surface the caller's mistake.
    """
    if not (0.0 <= core_weight <= 1.0):
        raise ValueError(f"core_weight must be within [0, 1], got {core_weight!r}")
    if not core_symbols and not satellite_symbols:
        raise ValueError("allocate_core_satellite: both core_symbols and satellite_symbols are empty")

    if not core_symbols:
        core_capital, satellite_capital = 0.0, total_capital
    elif not satellite_symbols:
        core_capital, satellite_capital = total_capital, 0.0
    else:
        core_capital = total_capital * core_weight
        satellite_capital = total_capital - core_capital

    allocation: dict[str, float] = {}
    if core_symbols:
        per_core = core_capital / len(core_symbols)
        for symbol in core_symbols:
            allocation[symbol] = allocation.get(symbol, 0.0) + per_core
    if satellite_symbols:
        per_satellite = satellite_capital / len(satellite_symbols)
        for symbol in satellite_symbols:
            allocation[symbol] = allocation.get(symbol, 0.0) + per_satellite
    return allocation
