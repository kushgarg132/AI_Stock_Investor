---
id: SPEC-intraday-strategies-expansion
companions: []
sources: []
---

> **Canonical contract.** This SPEC is the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Intraday Strategy Expansion

## Why

An opportunity to capture: the strategy engine has 5 longterm strategies but only 1 intraday strategy (`volume_surge`), even though the indicator toolkit (`backend/components/quant/indicators.py`) already implements VWAP, RSI, and ATR that no `Strategy` subclass currently uses. Closing this gap gives the suggestion/approval flow more intraday trade ideas to surface, using math that's already built and tested.

## Capabilities

- **CAP-1** VWAP Reversion
  - **intent:** System can flag an intraday mean-reversion trade when price deviates meaningfully from the session VWAP and starts reverting toward it.
  - **success:** Strategy emits a BUY/SELL `Intent` with `reason_codes` including `vwap_reversion`; backtested via `run_backtest` (`backend/engine/backtest.py`) with win-rate/drawdown reviewed and accepted by the user before being wired into `build_default_strategies()`.

- **CAP-2** Opening Range Breakout (ORB)
  - **intent:** System can flag a breakout trade when price clears the opening range high/low with volume confirmation.
  - **success:** Strategy emits a BUY/SELL `Intent` with `reason_codes` including `orb_breakout`; backtested and reviewed/accepted by the user before being wired into `build_default_strategies()`.

- **CAP-3** RSI Momentum Scalp
  - **intent:** System can flag a short-duration momentum trade when RSI crosses an overbought/oversold threshold with trend confirmation.
  - **success:** Strategy emits a BUY/SELL `Intent` with `reason_codes` including `rsi_momentum_scalp`; backtested and reviewed/accepted by the user before being wired into `build_default_strategies()`.

## Constraints

- Each strategy is a `TokenResolvingStrategy` subclass (`backend/strategies/base.py`) with a `StrategySpec` (`mode="INTRADAY"`, `timeframe="5m"`) and emits via `Intent` (`backend/core/models.py`) — same shape as `volume_surge.py`.
- No I/O, no `datetime.now()`, no network calls inside strategy modules — enforced by `backend/tests/test_no_datetime_now.py` and `test_no_network_in_strategies.py`; new files must pass both.
- Each strategy must be backtested via `backend/engine/backtest.py::run_backtest` on historical data, with results reviewed and accepted, before it is added to `build_default_strategies()` (`backend/strategies/registry.py`) — required gate, since a live-wired strategy can surface real-money suggestions through the approval flow.
- Every `reason_codes`, `stop_hint`, and `target_hint` must be justified by the strategy's own logic, per `Intent.__post_init__`'s "no rule hit, no intent" contract.

## Non-goals

- A 4th+ intraday strategy this round.
- Changes to longterm strategies.
- Changes to the suggestion/approval UI.
- New indicator math beyond what `Indicators` already provides (`rsi`/`vwap`/`atr`) — these three strategies reuse existing, currently-unused indicator functions.

## Success signal

- All 3 strategies pass `test_no_datetime_now.py` / `test_no_network_in_strategies.py`, have a unit test each, and have a completed backtest run whose results the user has reviewed and accepted. Only after acceptance are they added to `build_default_strategies()` so they can surface live suggestions.

## Assumptions

- Opening range window defaults to the first 15 minutes of the NSE session (09:15–09:30 IST) — standard ORB convention, not explicitly confirmed by the user.

## Open Questions

- Exact VWAP-deviation threshold, RSI overbought/oversold levels, and ORB range window are left to backtesting/tuning rather than fixed upfront — what thresholds clear the win-rate/drawdown bar is decided when each strategy is backtested.
