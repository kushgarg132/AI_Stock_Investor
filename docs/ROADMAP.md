# NeoTrade — roadmap

One phase per working session. Each phase states its goal, why it sits where it does, the
files it touches, and **done-when** criteria you can check yourself against before claiming
it finished.

Update the Status column when a phase lands. That column is how a future session knows
where to start — nothing else in this repo tracks it.

| Phase | Goal | Blocked by | Status |
|---|---|---|---|
| 0 | Rename to NeoTrade | — | **done 2026-09-09** |
| 1 | Multi-tenancy security | — | **done 2026-09-09** |
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

## Phase 0 — Rename to NeoTrade — **done 2026-09-09**

### Where things live now

| | |
|---|---|
| Repo | `github.com/kushgarg132/NeoTrade` |
| Working clone | `/home/ubuntu/projects/NeoTrade` |
| Deploy clone | `/home/ubuntu/deploys/NeoTrade` |
| Backend | `https://neotrade.161.118.167.148.nip.io` (port 8000, container `neotrade-backend`) |
| Frontend | `https://neotrade-trading.vercel.app` (Vercel project `neotrade`, root dir `frontend`) |
| Session keys | cookie `neotrade_refresh`, localStorage `neotrade_token` |
| Runner labels | `self-hosted, neotrade` (the old `aistock` label still exists on runner id 2) |

`ai-stock-investor.vercel.app` remains an alias on the same project and still serves the
current build — Vercel keeps the old project-name domain after a rename. It is still in the
backend's CORS allowlist. Drop both when you are sure nothing points at it.

The old `ai-stock.161.118.167.148.nip.io` subdomain is gone: Nginx site removed, cert deleted.

### Still outstanding — needs a human

**Google Cloud Console → Credentials → the OAuth client → Authorized JavaScript origins:**
add `https://neotrade-trading.vercel.app`. Until that is done, Google sign-in fails on the
new frontend URL (it still works on the `ai-stock-investor.vercel.app` alias, which was
already authorized). Nothing in the codebase can do this step.

### Notes for whoever hits similar work later

- Changing the compose project `name:` makes Compose treat the stack as new, so it will not
  stop the old containers — the first deploy failed with `Bind for :::8000 failed: port is
  already allocated` until `ai-stock-investor-backend` was removed by hand.
- The runner label was added via
  `gh api --method POST repos/.../actions/runners/2/labels -f "labels[]=neotrade"` *before*
  the workflow started asking for it, so no deploy was ever stranded without a runner.
- A repo rename does not disturb a registered self-hosted runner; it stayed online.
- `vercel deploy` must run from the repo root, not `frontend/` — the project's Root Directory
  is already `frontend`, so deploying from inside it fails with "Root Directory does not
  exist".
- A freshly-set `vercel.app` alias 302s to Vercel SSO for a minute or so before it settles
  and serves publicly. That redirect is not a protection misconfiguration; wait and re-check.
- Backend cold start blocks for ~60s seeding the instrument master before Uvicorn serves, so
  an immediate health check after deploy returns 502. Poll rather than concluding failure.

---

## Phase 1 — Multi-tenancy security — **done 2026-09-09**

A second human is now safe to add. What changed:

- **Broker credentials are per-user and encrypted** — `backend/auth/broker_credentials.py`,
  collection `broker_credentials`, Fernet-encrypted with `CREDENTIAL_ENCRYPTION_KEY`. The
  store refuses to save when that key is unset rather than writing plaintext. The API is
  write-only: reads return `{configured, api_key_masked}`, never the secret.
- **Broker sessions are per-user** — the cache key is
  `broker:{user_id}:kite:access_token`, not the old fixed `kite:access_token`.
- **`_write_env_vars` is gone**, with both endpoints that called it. Nothing writes `.env`
  or mutates the settings singleton at runtime; a test asserts the symbols no longer exist.
- **Roles exist** — `User.role`, `require_admin` in `backend/auth/dependency.py`, populated
  from `ADMIN_EMAILS` and re-derived on every login, so revoking is an env edit plus a
  re-login.
- **The LLM model moved to Mongo** (`backend/app_settings.py`) behind that admin check. It
  is genuinely deployment-wide, so it stays shared rather than becoming per-user. A
  process-level cache keeps it reaching the synchronous `get_llm()` without a restart.
- **`/trading/start` reads risk caps from `PrefsStore`** instead of the request body, which
  could previously size past the user's saved limits.

Deployment gained two env vars: `CREDENTIAL_ENCRYPTION_KEY` (Fernet) and `ADMIN_EMAILS`.
Both are wired through `docker-compose.yml`. Losing the encryption key means every stored
credential must be re-entered.

### Notes

- `cryptography` was only ever installed transitively; it is now declared in
  `backend/requirements.txt`, since the container build would otherwise be a coin flip.
- The old startup Kite instrument refresh was deleted rather than moved: credentials are
  per-user and at startup no user is in scope. It runs on broker connect instead, which is
  also when a fresh daily token exists.
- Still deliberately shared: the `instruments` master and the `sentiment:{symbol}` cache.
  Both are market-wide reference data, not personal.

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
