# AI Stock Investor — product truth

> Written by Impeccable `init` from the codebase and the operator's answers in
> the redesign session. Items marked *(assumed)* were inferred from code, not
> confirmed by interview.

## What it is

A personal, single-operator trading cockpit for **Indian equities (NSE)**. A
strategy engine watches a universe of stocks, sizes and scores its own trade
ideas, and either executes them (intraday) or hands them to the operator to
approve or reject (long-term). Everything is **paper traded** — no real money
moves. A connected Zerodha Kite session supplies live market data only.

## The mechanism nobody else has

The engine does not emit tickers, it emits **fully-formed trades**: a size, an
entry reference, a stop, a target, the rule codes that fired, and a composite
score whose AI component is structurally capped at 30% and cannot rescue a
trade the rules did not already support. Approving one places exactly the
trade the strategy asked for. The product's real claim is *legible machine
conviction* — you can always see why.

## Who uses it

One person: the operator, who is also the developer. Experienced enough to
read a stop-loss and an R:R ratio without explanation. Not a professional
trader — this runs alongside a day job.

## The real scene

**Mostly on a phone**, during the NSE session (09:15–15:30 IST), in short
glances: between meetings, on the move, at a desk only sometimes. The two
questions that matter in those glances are *"where am I today?"* and *"is
there anything waiting for me to decide?"*. Desktop is the occasional deep
session. **Phone is the design target; desktop is not a widened phone but it
is second.**

## Surfaces

| Surface | Mode | The visitor's success |
|---|---|---|
| Dashboard `/` | Operate | Search any stock and get full analysis + AI; see today/month P&L; see active and completed trades |
| Suggestions `/suggestions` | Operate | Triage pending AI proposals — approve or reject — split Intraday / Long-term |
| Portfolio `/portfolio` | Operate | Equity curve, open positions marked live, closed-trade history |
| Trading `/trading` | Operate | Start/stop an engine run, watch positions and fills |
| Watchlist `/watchlist` | Operate | Tracked symbols at a glance |
| Scanner `/scanner` | Operate | On-demand bullish scan results |
| Settings `/settings` | Operate | Broker connection, scan universe, risk caps, AI model |
| Login `/login` | Operate | Google sign-in, nothing else |

## States that matter more than the happy path

- **Nothing pending.** The common case. An empty inbox must read as "you're
  clear", not as a broken page.
- **Live vs stale.** Data arrives over a WebSocket. The operator must always
  know whether a number is live, stale, or the socket is down — a stale P&L
  presented as current is the worst failure this product has.
- **Market closed.** Most hours of most days. Prices do not move; the UI
  should say so rather than implying a frozen feed.
- **Decision pending, expiring.** Long-term suggestions expire after ~3 days.
- **Broker disconnected.** Kite tokens die daily at 06:00 IST.
- **Loss.** Red numbers are a normal, frequent state, not an error condition.

## Constraints

- React 19 + Vite, plain JSX (no TypeScript), Tailwind v4, React Router 7.
- Existing deps that stay: recharts, framer-motion, lucide-react, axios.
- No component library and no test runner on the frontend.
- Bearer token in `localStorage`; backend on `*.nip.io`, frontend on Vercel.
- INR (₹) throughout. IST for every day boundary.

## Brand commitments

None. There is no logo, no brand palette, no external identity to honour.
The visual world is free.

## Explicitly not this product

Not a broker. Not social. Not a signal-selling service. No gamification of
wins, no streaks, no confetti on a profitable trade — this is someone's money
model, and a design that celebrates a green day will feel like mockery on a
red one.
