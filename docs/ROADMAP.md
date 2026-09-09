# NeoTrade — roadmap

One phase per working session. Each phase states its goal, why it sits where it does, the
files it touches, and **done-when** criteria you can check yourself against before claiming
it finished.

Update the Status column when a phase lands. That column is how a future session knows
where to start — nothing else in this repo tracks it.

| Phase | Goal | Blocked by | Status |
|---|---|---|---|
| 0 | Rename to NeoTrade | — | not started |
| 1 | Multi-tenancy security | — | not started |
| 2 | Broker adapter layer | 1 | not started |
| 3 | Safety rails + backtest gate | — | not started |
| 4 | Wire the three intraday strategies | 3 | not started |
| 5 | Live execution + F&O | 1, 2, 3 | not started |
| 6 | Revive the long-term agent engine | — | not started |
| 7 | Multi-worker readiness | — | not started |

Two orderings are not negotiable: **Phase 3 before Phase 5** (no real order may be
placeable before the kill-switch and the gate exist), and **Phase 1 before anything that
touches broker credentials**.

---

## Phase 0 — Rename to NeoTrade

**Goal.** Remove the old name from code, config, docs, and infrastructure, so nothing
inherits the naming debt.

**Code identifiers** — these do not match a grep for the product name, and each logs every
existing session out when changed, which is acceptable but should be deliberate:

- `REFRESH_COOKIE_NAME = "asi_refresh"` — `backend/configs/settings.py:56`
- `TOKEN_STORAGE_KEY = 'asi_token'` — `frontend/src/utils/api.js:36`

**Strings and config:** `backend/configs/settings.py:7` (`PROJECT_NAME`),
`backend/server.py:41-42,64,98,153`, `frontend/index.html:9`,
`frontend/src/components/layout/Masthead.jsx:60`,
`frontend/src/components/layout/Sidebar.jsx:17`, `frontend/src/pages/Login.jsx:31`,
`frontend/src/index.css:2`, `docker-compose.yml:1,14,41`, `.github/workflows/ci.yml:85`,
`_bmad/bmm/config.yaml:13`, `_bmad/core/config.yaml:7`.

**Infrastructure — confirm each with the operator before running it:**

- GitHub repo rename (git remotes keep working via GitHub's redirect, but fix them anyway).
- Vercel project rename — orphans `.vercel/project.json` in both the repo root and
  `frontend/`; both are linked to the same project.
- New nip.io subdomain, Nginx site, and Certbot cert.
- `frontend/vercel.json:5` rewrite destination — this proxy is what keeps the refresh cookie
  first-party for Safari/Firefox, so getting it wrong breaks login silently.
- The WebSocket host in `frontend/src/lib/ws.js` — exempt from the Vercel rewrite, points at
  the backend directly.
- `CORS_ALLOWED_ORIGINS` in `.env`.
- Google Cloud Console → authorized JavaScript origins (add the new frontend origin).
- Self-hosted runner label `aistock` and deploy path
  `/home/ubuntu/deploys/AI_Stock_Investor` — `.github/workflows/deploy-backend.yml:29,37,58,63`.
- The project table in this VM's `/home/ubuntu/CLAUDE.md`.
- `render.yaml` looks like dead config from the pre-VM era — confirm, then delete.

**Done when:** `rg -i "ai.stock.investor|asi_|onrender"` returns only intentional historical
references; login works end to end on the new domain (a real sign-in, not just a health
check); the deploy workflow completes a push-triggered deploy on the renamed repo.

---

## Phase 1 — Multi-tenancy security

**Goal.** Make a second human safe to add. Today any signed-in user can overwrite everyone's
broker credentials.

**Why now:** this is the only phase whose absence is actively dangerous, and every later
phase touches broker credentials.

**Work:**

- Delete `_write_env_vars` (`backend/routers/settings.py:77-96`) and the endpoints that call
  it (`:99-116`, `:119-144`). Runtime configuration must never rewrite `.env` on disk or
  mutate the `settings` singleton.
- Move broker credentials into a per-user Mongo document, encrypted at rest, with the key
  from the environment. Never returned to the client — write-only, with a boolean
  "connected" state for display.
- Scope the broker session cache by user: the fixed Redis key `kite:access_token`
  (`backend/auth/kite_session.py:42`) becomes `broker:{user_id}:{broker}:access_token`.
- Rebuild `KiteSessionManager` construction (`backend/routers/broker.py`,
  `backend/routers/trading.py:99-122`) to take the caller's credentials rather than
  `settings`.
- Add a role field to `User` and an admin dependency for anything deployment-wide.
- Read risk caps from `PrefsStore` in `/trading/start` instead of trusting the request body
  (`routers/trading.py:158-215`) — match what `scheduler.py:52-59` already does correctly.

**Done when:** two different users can connect two different Kite accounts simultaneously
and neither sees the other's data or can alter the other's credentials; a test asserts a
non-admin cannot reach any deployment-wide setting; no code path writes `.env`.

---

## Phase 2 — Broker adapter layer

**Goal.** One interface, three brokers.

**Work:** define `BrokerAdapter` covering credential/token lifecycle, market data, and order
placement. Port Kite onto it (`backend/data/providers/kite_provider.py`,
`backend/data/feeds/live_kite.py`, `backend/auth/kite_session.py`,
`backend/instruments/kite_source.py`). Add Upstox and Angel One (SmartAPI). Keep the
existing `MarketDataProvider` seam (`backend/data/protocols.py:7-9`) — it already works;
the adapter composes with it rather than replacing it.

**Done when:** a user can connect any of the three brokers from Settings and receive live
marks through it; no module outside the adapter package imports a broker SDK; adding a
fourth broker requires no change outside its own adapter file.

---

## Phase 3 — Safety rails + backtest gate

**Goal.** Make the two non-negotiable protections real before any real order can exist.

**Work:**

- **Daily loss kill-switch**: halts live trading for the rest of the session once
  realized + unrealized loss crosses the user's configured limit. Does not re-arm on its
  own; surfaces as a first-class UI state (see `PRODUCT.md`).
- **Per-trade and per-day capital caps**, enforced inside `size_intents`
  (`backend/engine/runner.py:50-143`) so no caller can route around them.
- **Backtest gate**: persist dated `BacktestResult`s per strategy and refuse to run a
  strategy live unless its stored result meets the criteria below. Requires computing
  `max_drawdown` and `sharpe_ratio`, which are hardcoded `0.0` today
  (`backend/engine/backtest.py:94-95`).

**Proposed gate criteria — confirm before implementing:** backtest window ≥1 year, ≥30
trades, profit factor ≥1.3, max drawdown ≤15%.

**Done when:** a strategy without a passing stored backtest cannot be started in live mode,
proven by a test; tripping the loss limit halts trading and the state is visible in the UI;
drawdown and Sharpe are real numbers.

---

## Phase 4 — Wire the three intraday strategies

**Goal.** Put `VWAPReversionStrategy`, `ORBStrategy` and `RSIMomentumScalpStrategy` into
`backend/strategies/registry.py:16-59` — the only thing keeping them out of live trading
today is their absence from that list.

Backtests from the session that wrote them: VWAP Reversion was profitable on a thin sample
(2 trades); ORB and RSI Momentum Scalp were both negative and were then tuned without
re-validation. Treat all three as unproven — Phase 3's gate is what decides, not this note.

`backend/tests/test_strategies_ported.py:357-359` hard-codes
`len(strategies) == 4` and will fail; update it deliberately rather than deleting the
assertion.

**Done when:** each of the three has a stored backtest result, the gate's verdict on each is
recorded, and only the ones that passed are live-eligible.

---

## Phase 5 — Live execution + F&O

**Goal.** Real orders, and derivatives.

**Work:**

- `BrokerExecutionClient` implementing `ExecutionClient`
  (`backend/engine/protocols.py:49-53`) over `BrokerAdapter`, alongside the simulated one.
- Order state machine: submitted → acknowledged → partially filled → filled / rejected /
  cancelled. Idempotent submission so a retry cannot double-place.
- Reconciliation: the broker's own fills and positions are the source of truth, not the
  local `Portfolio`. Reconcile on startup and on reconnect.
- Per-user, per-strategy paper/live toggle. Replace the `TRADING_LIVE_ENABLED` dead-man's
  switch (`routers/trading.py:164-168`).
- Instrument model widens to `(symbol, exchange, instrument_type, lot_size, expiry, strike,
  option_type)`; sizing becomes lot-aware and margin-aware; positions gain expiry handling.

**Done when:** a live order placed by the engine appears in the broker's own order book and
reconciles back into the ledger with matching quantity and price; a deliberately rejected
order leaves the local book unchanged; an F&O position sizes in whole lots and respects
margin.

---

## Phase 6 — Revive the long-term agent engine

**Goal.** Give long-term suggestions a genuine reasoning source instead of reusing the
intraday rule strategies.

**Work:** rebuild the Analyst/Quant/Risk chain (currently dead —
`backend/components/quant/agent.py`, `backend/components/risk/agent.py`) so it emits
`Intent` and is scored by `backend/scoring/composite.py` like every other source. Its old
`confidence*0.6 + alignment*0.4` blend (`components/risk/agent.py:95-99`) must **not** come
back — that duplicate conviction formula is what the 30% cap exists to prevent. Delete
`backend/components/quant/strategies.py`, whose `TradeSignal` shape is superseded.

**Done when:** long-term suggestions carry agent-derived reasoning in `reason_codes`, the
AI contribution is still capped at 30%, and exactly one conviction formula exists in the
codebase.

---

## Phase 7 — Multi-worker readiness

**Goal.** Survive more than one backend worker.

**Work:** Redis pub/sub fan-out for the WS hub (`backend/ws/hub.py:9-10` already flags
this); a distributed lock for the scheduler (`backend/scheduler.py:8-10`); running engine
loops out of the process-local `_RUNS` dict (`backend/routers/trading.py:53`); make the
`llm_service` singleton (`backend/llm.py:125`) request-scoped so the per-user
`omniroute_model` pref stops being dead.

**Done when:** the backend runs with two workers and a user connected to one sees live
updates produced by the other.
