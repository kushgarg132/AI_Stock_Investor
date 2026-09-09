# NeoTrade

A trading cockpit for Indian equities and F&O. A strategy engine emits fully-formed trades —
size, entry, stop, target, the rule codes that fired, and a composite score — then either
executes them (intraday) or routes them to an approval inbox (long-term). Each user connects
their own broker (Kite / Upstox / Angel One) and chooses per strategy whether it trades on
paper or with real money.

FastAPI + MongoDB + Redis backend on this VM; React 19 + Vite frontend on Vercel.

## Read these, in this order

| Question | Document |
|---|---|
| What is this product, who uses it, what are the states that matter? | `PRODUCT.md` |
| How does the code actually work, and where is it going? | `docs/ARCHITECTURE.md` |
| **What should I work on right now?** | `docs/ROADMAP.md` — check the Status column |
| What should this look like? | `DESIGN.md` (tokens are real, in `frontend/src/index.css`) |

`docs/ARCHITECTURE.md` §1 is verified against the code with file:line anchors. If it and the
code disagree, the code is right — fix the document in the same commit.

## Invariants — never break these silently

- **AI is capped at 30% of conviction.** `AI_CAP = 0.30`, clamped inside a frozen dataclass
  at `backend/scoring/composite.py:15,25-30`. Not a convention — enforced and tested.
- **AI cannot rescue a trade the rules did not support.** `RULE_FLOOR = 0.45`;
  `score_intent()` returns `None` below it.
- **Exactly one conviction formula exists.** Any new idea source emits `Intent` and is scored
  by `composite.py`. Never add a second blend.
- **Every intent carries non-empty `reason_codes`.** A trade with no explanation cannot exist.
- **Every per-account record carries `user_id`.** This app is multi-user; nothing may be
  keyed on "the operator".
- **Position sizing lives in `size_intents` + `RiskRules`, never inside a strategy.**
- Once Phase 3 lands: the daily loss kill-switch and the backtest gate are enforced in code,
  not by discipline. Do not add a code path that routes around either.

## Deployment

Backend runs on this VM under Docker Compose behind Nginx + Let's Encrypt; frontend on
Vercel. Both halves are push-to-deploy from `main` — the backend via a self-hosted GitHub
Actions runner (gated on CI passing, rebuilds only when `backend/` or `docker-compose.yml`
changed), the frontend via Vercel's git integration. **Prefer the pipeline over deploying by
hand**; verify with `gh run watch <id> --exit-status` plus a health check rather than racing
it with a manual build. See `/home/ubuntu/CLAUDE.md` for ports, URLs, and host-level detail.

## Working here

- System `mvn` is irrelevant here; this is Python. Backend tests: `cd backend && python -m pytest`.
- `vitest` alone is not a build check on the frontend — run `npm run build` too.
- Background long builds and test runs rather than idling on them.
- Commit and push in the same session; split unrelated changes into separate commits.
