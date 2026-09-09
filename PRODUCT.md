# NeoTrade — product truth

> What this product is and who it serves. For how it is built, see
> [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); for what gets built next, see
> [`docs/ROADMAP.md`](docs/ROADMAP.md).

## What it is

A trading cockpit for **Indian equities and F&O**. A strategy engine watches a universe of
instruments, sizes and scores its own trade ideas, and either executes them (intraday) or
hands them to the trader to approve or reject (long-term). Each user connects their own
broker account — Zerodha Kite, Upstox, or Angel One — and chooses per strategy whether it
trades on paper or with real money.

## The mechanism nobody else has

The engine does not emit tickers, it emits **fully-formed trades**: a size, an entry
reference, a stop, a target, the rule codes that fired, and a composite score whose AI
component is structurally capped at 30% and cannot rescue a trade the rules did not already
support. Approving one places exactly the trade the strategy asked for. The product's real
claim is *legible machine conviction* — you can always see why.

That cap is not a policy, it is enforced in the type system and covered by tests. See
`docs/ARCHITECTURE.md` §1.2.

## Who uses it

Today: one person, the operator, who is also the developer — experienced enough to read a
stop-loss and an R:R ratio without explanation, running this alongside a day job.

Where it is going: other traders, on their own broker accounts, with their own portfolios.
The trajectory is deliberate — auth, per-user data scoping, and per-user broker sessions are
built for it rather than retrofitted. It is free, and monetization is not being designed for
until there are real users.

## The real scene

**Mostly on a phone**, during the NSE session (09:15–15:30 IST), in short glances: between
meetings, on the move, at a desk only sometimes. The two questions that matter in those
glances are *"where am I today?"* and *"is there anything waiting for me to decide?"*.
Desktop is the occasional deep session. **Phone is the design target; desktop is not a
widened phone but it is second.**

Once real money is in play, a third question joins them: *"is anything running that I should
stop?"*

## Surfaces

| Surface | Mode | The visitor's success |
|---|---|---|
| Dashboard `/` | Operate | Search any stock and get full analysis + AI; see today/month P&L; see active and completed trades |
| Suggestions `/suggestions` | Operate | Triage pending AI proposals — approve or reject — split Intraday / Long-term |
| Portfolio `/portfolio` | Operate | Equity curve, open positions marked live, closed-trade history |
| Trading `/trading` | Operate | Start/stop an engine run, watch positions and fills, see whether the run is paper or live |
| Watchlist `/watchlist` | Operate | Tracked symbols at a glance |
| Scanner `/scanner` | Operate | On-demand bullish scan results |
| Settings `/settings` | Operate | Broker connection, scan universe, risk caps and kill-switch limit, per-strategy paper/live mode, AI model |
| Architecture `/system` | Explain | A live view of how the system fits together |
| Login `/login` | Operate | Google sign-in, nothing else |

## States that matter more than the happy path

- **Nothing pending.** The common case. An empty inbox must read as "you're clear", not as a
  broken page.
- **Live vs stale.** Data arrives over a WebSocket. The trader must always know whether a
  number is live, stale, or the socket is down — a stale P&L presented as current is the
  worst failure this product has.
- **Live mode armed.** Real money can move without further approval. This must be
  unmistakable at a glance and never inferable only from a settings page.
- **Kill-switch tripped.** The daily loss limit was hit and live trading has halted for the
  session. It does not re-arm on its own. The UI must say what stopped, when, and what is
  still open.
- **Market closed.** Most hours of most days. Prices do not move; the UI should say so
  rather than implying a frozen feed.
- **Decision pending, expiring.** Long-term suggestions expire after ~3 days.
- **Broker disconnected.** Kite tokens die daily at 06:00 IST; other brokers have their own
  expiries.
- **Loss.** Red numbers are a normal, frequent state, not an error condition.

## Constraints

- React 19 + Vite, plain JSX (no TypeScript), Tailwind v4, React Router 7.
- Existing deps that stay: recharts, framer-motion, lucide-react, axios.
- No component library and no test runner on the frontend.
- Bearer token in `localStorage`; refresh token in an httpOnly cookie, kept first-party by a
  Vercel rewrite. Backend on `*.nip.io`, frontend on Vercel.
- INR (₹) throughout. IST for every day boundary.

## Brand commitments

The visual world is already built and real in code — a broker's contract note, kept live.
See [`DESIGN.md`](DESIGN.md); its tokens are implemented in `frontend/src/index.css`, not
merely documented. New surfaces inherit it rather than inventing.

## Explicitly not this product

Not a broker — NeoTrade routes orders through the user's own broker and holds no funds. Not
social. Not a signal-selling service: no user's trades or scores are visible to another, and
nothing here is published as advice. No gamification of wins, no streaks, no confetti on a
profitable trade — this is someone's money model, and a design that celebrates a green day
will feel like mockery on a red one.

Once real orders are possible, one more rule: the product never places a trade the user
cannot reconstruct after the fact. Every live fill traces back to the intent, the rule codes,
and the score that produced it.
