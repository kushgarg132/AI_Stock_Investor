# Phase 5b (F&O) — cash-secured put strategy — design

Status: approved by user 2026-09-11, pending implementation plan.

## Goal

ROADMAP.md Phase 5b asks for three things: a widened `Instrument` model for derivatives,
lot-aware and margin-aware sizing, and position expiry handling. Doing that plumbing with
nothing exercising it would be unverifiable, so this phase also ships one real strategy end
to end: a cash-secured put (CSP) writer, as a new LONGTERM (human-approval-inbox) signal
source alongside the four existing ones.

## Non-goals

- **No live broker order placement for F&O.** Investigated during design: LONGTERM
  suggestions never reach a real broker even on approval —
  `backend/suggestions/service.py::execute_suggestion` synthesizes a paper fill directly into
  the local ledger at the current mark price, for every existing LONGTERM strategy today, not
  just this one. This phase does not change that. `BrokerAdapter.place_order` and the three
  adapters are untouched.
- **No backtest-gate interaction.** The gate (`backend/risk/backtest_gate.py`) only filters
  `live_eligible_strategies` in `/trading/start`'s INTRADAY live/paper toggle. LONGTERM
  strategies (`backend/suggestions/scan.py::scan_universe`) are never filtered by it — none of
  the four existing LONGTERM strategies are gated today, and CSP isn't either. This is
  existing behavior, not a carve-out added here.
- **No covered call.** CSP alone is the "one real strategy" for this phase. Covered call is a
  natural follow-on once CSP's primitives (resolver, pricer, options sizing) exist, but needs
  its own trigger logic (against an existing long position) and isn't built here.
- **No real option-chain data.** No live broker account exists to query one (same constraint
  Phase 5a operated under for all three broker adapters). Strike/expiry selection is a
  deterministic calculator, not a live chain lookup; premium is a Black-Scholes estimate, not
  a market quote. Both are labeled as estimates everywhere they surface.
- **No exact Indian options tax/margin formulas.** Approximated and documented, same
  "advisory, not authoritative" posture the existing equity cost model
  (`backend/engine/execution/costs.py`) already states about itself.

## Architecture

### 1. Instrument model + contract resolution

`backend/instruments/models.py::Instrument` gains three new optional fields, all defaulting
to `None` (no migration, existing equity rows unaffected):

```python
expiry: Optional[date] = None
strike: Optional[float] = None
option_type: Optional[Literal["CE", "PE"]] = None
```

New `backend/options/resolver.py`:

- `next_monthly_expiry(today: date) -> date` — NSE's last-Thursday-of-month rule (rolls to the
  next month if the current month's has already passed or is within a minimum days-to-expiry
  floor).
- `nearest_strike(spot: float, otm_pct: float, strike_interval: float) -> float` — rounds
  `spot * (1 - otm_pct)` to the nearest multiple of `strike_interval` (strike intervals are
  standardized per underlying, e.g. 50 for most large-caps around a few thousand rupees; a
  small static table for the curated F&O universe below, not a general formula — NSE doesn't
  publish one).
- `format_tradingsymbol(underlying, expiry, strike, option_type) -> str` — NSE's
  `SYMBOL + YYMMM + STRIKE + CE/PE` convention (e.g. `RELIANCE24DEC2800PE`).
- `resolve_contract(master: InstrumentMaster, underlying, expiry, strike, option_type) ->
  Optional[Instrument]` — looks up the formatted tradingsymbol in the shared instrument
  master under exchange `NFO`.

Populating the master's `NFO` rows reuses existing infrastructure rather than adding new sync
machinery: `backend/instruments/loader.py::refresh_instruments_from_adapter` already takes an
`exchanges: tuple[str, ...]` parameter (default `("NSE", "BSE")`). Calling it with
`exchanges=("NFO",)` on broker connect — one call added where equity refresh already happens
— populates real `instrument_token`/`lot_size`/`tick_size` rows for whichever broker is
connected, via the adapter's existing generic `instruments(exchanges=...)` method. No broker
connected means no NFO rows means `resolve_contract` returns `None` means the CSP strategy
silently produces no suggestions that day — the same "no floor for what we don't have" posture
`SeedFileSource` already documents for equities, just without an equivalent options seed file.

### 2. Premium + margin estimate

New `backend/options/pricing.py`:

- `black_scholes_put(spot, strike, days_to_expiry, iv, risk_free_rate=0.07) -> float` — pure,
  standard formula, no I/O.
- `realized_volatility(closes: list[float], window: int = 20) -> float` — annualized stdev of
  daily log returns from the underlying's own existing yfinance daily bars (no new data
  source), used as the IV input above. This is a realized-vol proxy, not implied vol; labeled
  as an estimate in every place it's surfaced (suggestion card, stored document).
- `estimate_margin(spot, strike, premium, lot_size) -> float` — tries the connected broker's
  own margin endpoint first if the adapter exposes one (needs a real per-adapter check during
  implementation — Kite's SDK has `basket_order_margins`; Upstox/Angel One need verifying
  against their actual docs/SDK, same verification discipline every existing adapter docstring
  in this codebase already follows). Falls back to a flat 15% of contract notional
  (`strike * lot_size`) when no broker is connected or the call fails — a conservative,
  documented approximation, not a SPAN replica.

Both values are advisory: shown to the human on the suggestion card, never used to gate or
auto-size anything the way equity `size_intents` uses a real stop price.

### 3. Strategy, sizing, and the existing suggestion pipeline

`backend/core/models.py::Intent` gains one new optional field:

```python
option_flavor: Optional[Literal["CSP"]] = None
```

Every existing strategy constructs `Intent` without it; default `None` means zero behavior
change anywhere else. `__post_init__`'s validation is untouched.

New `backend/strategies/longterm/cash_secured_put.py::CashSecuredPutStrategy` (`mode =
"LONGTERM"`): reuses the oversold/support entry condition already implemented in
`backend/strategies/longterm/mean_reversion.py::MeanReversionStrategy` — "I'd be happy to own
this stock cheaper" is exactly what a CSP expresses — but instead of an `Intent` for the
underlying equity, emits one with `option_flavor="CSP"`. Universe is a small, curated,
hardcoded F&O-eligible subset (NSE F&O covers roughly 180 names; most of
`ALL_SCAN_STOCKS`'s mid/small-caps aren't eligible), living next to the strike-interval table
in `resolver.py`.

`backend/engine/runner.py::size_intents` gains one early branch, immediately after the
kill-switch check and before the existing stop-distance sizing code:

```python
if intent.option_flavor is not None:
    order = await size_option_intent(intent, scored, ctx, redis, account_size, master)
    if order is not None:
        proposal = Proposal(order=order, intent=intent, score=scored, entry=order_premium, mode=mode)
        ...  # same order_sink handoff the equity path already does
    continue
```

The existing equity path (`RiskRules.calculate_position_size`, stop_hint requirement, share
whole-numbering) is untouched — option-flavored intents never reach it. New
`backend/options/sizing.py::size_option_intent`: resolves the contract (section 1), prices it
(section 2), then sizes lots off a collateral budget — `BASE_RISK_PCT * scored.final` fraction
of `account_size` as max collateral, `lots = floor(budget / (strike * lot_size))`, capped at a
small default max lots/trade (e.g. 2), skipped if even one lot's collateral exceeds the
budget. Produces a normal `Order` whose `symbol` is the *option's own* tradingsymbol (not the
underlying's) and `product` — `Order.product`'s `Literal["CNC", "MIS"]` widens to include
`"NRML"` for this case, kept broker-realistic even though nothing calls a broker with it this
phase, so it costs nothing later if F&O live execution is ever built.

`owner_by_symbol.get(intent.symbol)` (used for `mode`/`strategy_name` attribution) keys off
`intent.symbol`, which stays the **underlying's** tradingsymbol — only the produced `Order`'s
symbol is the option contract. No change needed to `owner_by_symbol` construction.

This rides the existing `scan_universe` → `SuggestionSink` → `SuggestionStore` → approval
inbox pipeline structurally unchanged. `SuggestionStore.create` gets one small addition: when
`intent.option_flavor` is set, attach an `option_contract` dict (strike, expiry, option_type,
premium_estimate, margin_estimate, underlying_spot) to the stored document, so the UI can
render a real contract instead of just a symbol/side/quantity row.

`backend/suggestions/service.py::execute_suggestion` gets a small options-aware branch for the
paper fill: a new `backend/engine/execution/options_costs.py::calculate_options_costs`
(same shape as the existing equity cost model — brokerage, STT on the sell/write side, GST —
approximated and documented as such, not the exact regulatory formula) replaces
`calculate_indian_costs` when the suggestion carries `option_contract`. `Portfolio.apply`
needs no change — its signed-quantity/avg-price math already generalizes to a short option
position the same way it already handles short equity.

### 4. Expiry handling

Fourth job in `backend/scheduler.py::run_daily_jobs`, alongside the existing scan/sentiment-
refresh/stale-suggestion-expiry jobs: `close_expired_option_positions` finds open positions
whose symbol resolves (via the instrument master) to a row with `expiry` in the past, and
books a closing paper fill — worthless (premium → 0) if OTM at the last available mark, a
documented simple intrinsic-value approximation if ITM (not real physical/cash assignment
mechanics, which NSE's actual settlement rules are more involved than is worth modeling for a
paper-only strategy).

## Testing

Matches this codebase's existing pattern throughout `backend/tests/`: pure functions
(`resolver.py`'s strike/expiry math, `pricing.py`'s Black-Scholes and realized-vol, `sizing.py`'s
lot math) get direct unit tests with no I/O. `size_intents`'s new branch and
`execute_suggestion`'s options branch get the same mocked-fixture style as their existing
tests. No live broker account exists to test any margin-endpoint call against — same posture
every adapter docstring in this codebase already states about itself; the flat-% fallback path
is what's actually exercised in tests.

## Done when

- `Instrument`, `Order`, and `Intent` carry the new optional fields with every existing test
  still passing unchanged.
- A connected broker's NFO instrument dump populates the instrument master via the reused
  `refresh_instruments_from_adapter(exchanges=("NFO",))` call.
- `CashSecuredPutStrategy` produces a suggestion with a real resolved contract (strike, expiry,
  tradingsymbol), an estimated premium, and an estimated margin, when a broker is connected
  and its trigger condition fires.
- Approving that suggestion produces a paper fill and a short option `Position` in the ledger,
  using the options cost model.
- A position whose contract has expired is closed out by the scheduler job on its next daily
  run.
- Full backend suite passes.
