# Google Login (core auth)

## Context

AI_Stock_Investor currently has zero auth/user concept anywhere: no session
middleware in `backend/server.py`, no user model in Mongo, CORS is
`allow_origins=["*"]` with `allow_credentials=True` (a technically-invalid
combo — browsers reject real credentialed cross-origin requests against a
wildcard origin), and the only place a "user" exists at all is a hardcoded
`"default-user"` string used as the Watchlist owner
(`frontend/src/pages/Watchlist.jsx:13`, `frontend/src/components/AnalysisCard.jsx:71`).
The Sidebar footer even renders a fake static "Pro Investor" card that isn't
wired to anything real.

The user wants the whole app to require Google sign-in — no page loads
without a session. This surfaced a bigger decision along the way: with open
signup (any Google account, not an allowlist), the `/trading/*` control
plane and the OmniRoute model picker built earlier this session are
currently **global singletons** with no per-user partitioning — two signed-in
accounts would share the exact same paper-trading positions/fills/model
selection. The user confirmed both of those should eventually become
per-user too, but that can't be built before auth itself exists, so this
project is split in three:

1. **This spec: Google auth core** — login flow, session verification, page
   gating, and the (already-trivial) per-user Watchlist swap.
2. *(separate, later spec)* Per-user `/trading/*` — `LedgerStore`/positions/
   fills scoped by user, the in-memory `_RUNS` dict keyed by user.
3. *(separate, later spec, likely folded into #2)* Per-user OmniRoute model
   preference.

## Scope

**In scope:**
- A dedicated new Google OAuth client (not reusing RoutineOS's) — clean
  branding on the consent screen, no shared blast radius with another
  project's credentials.
- Open signup — any Google account can sign in and gets its own Watchlist.
- Google Identity Services ID-token flow (implicit, not authorization-code)
  — no client secret needed anywhere in this flow, only **Authorized
  JavaScript origins** in Google Cloud Console, no redirect URI. Same
  pattern RoutineOS's "Sign-In" half already uses in production on this
  VM (its separate Calendar/Drive integration is authorization-code +
  client-secret, a distinct concern this app doesn't need).
- Backend verifies the ID token, upserts a `User` document, issues its own
  **bearer JWT returned in the response body** (not a cookie — see
  "Session transport" below), 7-day expiry, no refresh tokens for v1 —
  re-login via the Google button when it lapses.
- Every existing route gated behind a `get_current_user` FastAPI dependency,
  applied via `include_router(..., dependencies=[...])` in `server.py` —
  not by touching every individual router file.
- Every existing frontend route gated behind a `RequireAuth` wrapper in
  `App.jsx` — not by touching every individual page.
- Fixing the CORS `allow_origins=["*"]` + `allow_credentials=True` combo
  into an explicit origin allowlist (required for cookies to actually work
  cross-origin, not an optional cleanup).
- Watchlist's existing `user_id` field gets the real signed-in user's id
  instead of `"default-user"` — no schema change, since it already has this
  field.
- Sidebar's fake "Pro Investor" footer replaced with the real user's
  name/picture/email and a working logout button.

**Out of scope (confirmed, deferred to later specs):**
- Per-user `/trading/*` scoping (spec #2).
- Per-user OmniRoute model preference (spec #3).
- Refresh tokens / "remember me" beyond a flat 7-day session.
- Any role/permission system beyond "logged in or not" — no admin vs.
  regular user distinction.
- An allowlist of specific emails — explicitly rejected in favor of open
  signup.

## Session transport: bearer JWT, not a cookie

RoutineOS (a sister project on this same VM, already running Google
sign-in in production) deliberately avoids cookie-based sessions entirely:
its `SecurityConfig` is stateless (`SessionCreationPolicy.STATELESS`), the
backend never sets a `Set-Cookie` header, and the frontend stores the JWT
itself (localStorage on web, native secure storage on mobile), attaching it
via `Authorization: Bearer <token>` through an axios interceptor. This
sidesteps the exact cross-origin cookie complexity this project would
otherwise have to get right — `SameSite=None` + `Secure` + explicit CORS
origins — since the Vercel frontend and the nip.io-fronted backend are
different origins. Following that proven pattern here:

- `POST /auth/google` returns `{token: str, user: {...}}` in the JSON body
  — no `Set-Cookie` anywhere.
- Frontend stores the token in `localStorage` and attaches it via an axios
  **request** interceptor (`Authorization: Bearer <token>`), not cookie
  jar behavior.
- `get_current_user` reads `Authorization: Bearer <token>` from the
  request header (FastAPI's `HTTPBearer` security scheme), not a cookie.
- A response interceptor on the frontend catches any 401 app-wide, clears
  the stored token, and redirects to `/login` — this is what makes "no
  page loads without a valid session" hold even mid-use, not just on
  initial load (mirrors RoutineOS's own 401-interceptor pattern).
- Accepted tradeoff (same one RoutineOS accepts on web): a token in
  localStorage is readable by any JS that runs on the page (XSS exposure),
  vs. httpOnly's script-inaccessibility. For a personal project with a
  small, known frontend codebase this is judged an acceptable tradeoff
  over the cookie-correctness risk it avoids.
- No CSRF concern either way — there's no ambient cookie credential for a
  cross-site request to ride on.

## Backend design

**New dependencies** (`backend/requirements.txt`): `google-auth` is already
present as a transitive dependency (confirmed via `pip show`) but not
declared directly — pin it directly since this feature now depends on it
by name (`google.oauth2.id_token.verify_oauth2_token`). This mirrors
RoutineOS's choice to use Google's own official client library for ID-token
verification rather than hand-rolling JWKS fetch/caching/rotation — the
Python equivalent of the Java `GoogleIdTokenVerifier` it uses in
production. `pyjwt` for signing/verifying the app's own session token (not
currently a dependency; `python-jose` is an alternative but `pyjwt` is
smaller and sufficient for HS256).

**New settings** (`backend/configs/settings.py`):
- `GOOGLE_CLIENT_ID: str` — the new dedicated OAuth client's ID (public,
  safe to also expose to the frontend via `VITE_GOOGLE_CLIENT_ID`).
- `JWT_SECRET: str` — this app's own signing secret, generated fresh via
  `openssl rand -base64 48`, **not** shared with RoutineOS's `JWT_SECRET`.
- `SESSION_MAX_AGE_SECONDS: int = 604800` (7 days).
- `CORS_ALLOWED_ORIGINS: List[str]` — replaces the wildcard; defaults to
  `["http://localhost:5173"]`, production value set via `.env` to the
  Vercel prod URL(s). Mirrors RoutineOS's own
  `routineos.cors.allowed-origins` pattern (an explicit env-driven list,
  never a wildcard, paired with `allow_credentials=True` — note
  `allow_credentials` is still needed even without cookies, for the
  `Authorization` header to be readable cross-origin and for the OPTIONS
  preflight to succeed under credentials mode).

**New module `backend/auth/`:**
- `backend/auth/google.py`: `async def verify_google_token(id_token: str) -> GoogleUserInfo` — wraps `google.oauth2.id_token.verify_oauth2_token`, raises `InvalidGoogleToken` on any verification failure (wrong audience, expired, bad signature). `GoogleUserInfo` is a small dataclass: `{sub, email, name, picture}`.
- `backend/auth/jwt.py`: `create_session_jwt(user: User) -> str` (encodes `{sub: user.id, exp: ...}` with `JWT_SECRET`, HS256), `decode_session_jwt(token: str) -> str` (returns the user id, raises `InvalidSessionToken` on expiry/tamper).
- `backend/auth/models.py`: `User` Pydantic model — `{id: str, google_sub: str, email: str, name: str, picture: Optional[str], created_at: datetime}`. `id` is a fresh UUID (not reused from Google's `sub`) so the app's user id is stable even if the auth provider ever changes.
- `backend/auth/dependency.py`: `async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> User` — decodes `credentials.credentials` (the bearer token), loads the `User` doc from Mongo by id, raises `HTTPException(401)` if the token is missing, invalid, expired, or the user no longer exists. `HTTPBearer()` itself already returns 403 if the `Authorization` header is missing entirely — both cases surface as a rejection the frontend's 401/403-handling interceptor treats identically.
- `backend/auth/store.py`: `UserStore` (Mongo-backed, collection `users`, unique index on `google_sub`) — `async def upsert_from_google(info: GoogleUserInfo) -> User` (find-by-`google_sub`-or-create). **New-user field parity**: this is the one and only place a `User` document is ever created in this app (unlike RoutineOS, which has both a password-registration path and a Google-login path that must be kept in sync — the exact bug RoutineOS hit when a field was added to one but not the other), so there's no parity risk here today. If a second account-creation path is ever added later, audit this function's field set against it explicitly. `async def get_by_id(user_id: str) -> Optional[User]`.

**New router `backend/routers/auth.py`:**
- `POST /auth/google` — body `{id_token: str}`. Verifies via `verify_google_token`, upserts via `UserStore.upsert_from_google`, creates a session JWT, returns `{token: str, user: {...}}` in the response body (no cookie — see "Session transport" above).
- `POST /auth/logout` — no server-side action needed for a stateless bearer JWT (there's no cookie to clear); this endpoint exists only for API symmetry/future extensibility (e.g. a server-side revocation list) — the frontend's actual logout is simply discarding the locally-stored token.
- `GET /auth/me` — depends on `get_current_user`; returns the current `User`, or FastAPI's normal 401/403 (from the dependency) if not authenticated. This is the endpoint the frontend calls once on load to check for an existing valid token.

**Gating existing routes** (`backend/server.py`): every `app.include_router(...)` call for existing routers (news, sentiment, events, price, support, trend, volume, risk, stock_info, stock_scanner, agents, chat, settings, market_data, watchlist, trading) gets `dependencies=[Depends(get_current_user)]` added. `auth.router` itself is mounted without this dependency (chicken-and-egg — you can't require a session to create one). Docs/OpenAPI routes (`/docs`, `/redoc`, `/openapi.json`) stay ungated so the API is still inspectable.

**CORS fix** (`backend/server.py`): replace
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, ...)
```
with
```python
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ALLOWED_ORIGINS, allow_credentials=True, ...)
```

**Watchlist**: no backend change — the router already takes `user_id` as a path param. Only frontend call sites change what they pass.

## Frontend design

**New dependency**: `@react-oauth/google` (thin wrapper around Google
Identity Services — avoids hand-rolling the raw JS SDK's script-tag/callback
dance).

- `frontend/src/main.jsx` (or `App.jsx`): wrap the app in
  `<GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>`.
- New `frontend/src/context/AuthContext.jsx`: `AuthProvider` component +
  `useAuth()` hook. On mount, reads a stored token from `localStorage`
  (key `asi_token`); if present, calls `GET /auth/me` to validate it — on
  200 sets `user`, on 401/403 clears the stored token and sets
  `user: null` (this is the normal "not logged in"/"expired" case, not an
  error — no destructive banner for it). Exposes
  `{user, loading, login(idToken), logout()}` — `login` posts to
  `/auth/google`, stores the returned token in `localStorage`, sets `user`
  from the response; `logout` clears the stored token and `user` state
  (no network call strictly required, though hitting `/auth/logout` for
  symmetry is harmless).
- New `frontend/src/pages/Login.jsx`: centered card with the app's existing
  dark-theme styling, renders `<GoogleLogin onSuccess={...} onError={...}>`
  from `@react-oauth/google`. On success, calls `useAuth().login(credentialResponse.credential)`, then navigates to `/`.
- New `frontend/src/components/RequireAuth.jsx`: wraps route elements —
  if `loading`, render a centered spinner (reuse the existing spinner
  pattern from `Dashboard.jsx`'s analysis-loading state); if `!user`,
  `<Navigate to="/login" replace />`; else render `children`.
- `frontend/src/App.jsx`: every existing `<Route>` element wrapped in
  `<RequireAuth>`, plus one new unwrapped `<Route path="/login" element={<Login />} />`.
- `frontend/src/utils/api.js`: add a **request interceptor** that reads the
  token from `localStorage` (key `asi_token`) and sets
  `Authorization: Bearer <token>` on every outgoing request (skipped only
  for `/auth/google`, which doesn't need one yet); add a **response
  interceptor** that on any 401/403 clears the stored token and redirects
  to `/login` (mirrors RoutineOS's own axios 401-interceptor pattern) —
  this is what makes an expired/invalidated session kick the user back to
  login mid-use, not just block it on next page load.
- `frontend/src/components/layout/Sidebar.jsx`: replace the hardcoded
  "Pro Investor / Pro Plan" footer block with the real user's
  `picture`/`name`/`email` from `useAuth()`, plus a working logout button
  (currently decorative — this footer exists today with zero click handler).
- `frontend/src/pages/Watchlist.jsx` and `frontend/src/components/AnalysisCard.jsx`: replace the hardcoded `"default-user"` string with `useAuth().user.id`.

## Error handling

- `verify_google_token` failure (expired/tampered/wrong-audience ID token)
  → `POST /auth/google` returns 401 with a clear detail message; frontend's
  `Login.jsx` shows an inline error, stays on the login page.
- `get_current_user` failure (missing/invalid/expired token) → 401/403 on
  any gated route; the response interceptor described above catches this
  app-wide and redirects to `/login` — this is what makes "no page loads
  without a session" actually hold even for a session that expires
  mid-use, not just on initial load.
- Google Identity Services itself failing to load (network/ad-blocker) →
  `<GoogleLogin onError={...}>` surfaces a visible "Sign-in failed, please
  try again" message rather than a silent dead button.

## Testing

- Backend (`backend/tests/test_auth.py`, new): `verify_google_token` mocked
  (don't hit Google's real key-fetch in unit tests) for valid/expired/
  wrong-audience cases; JWT create/decode round-trip; `get_current_user`
  dependency rejecting missing/invalid/expired bearer tokens via FastAPI's
  `TestClient`; `UserStore.upsert_from_google` idempotency (same
  `google_sub` twice returns the same `User.id`, doesn't duplicate).
- Backend integration: a `TestClient` request to any gated route (e.g.
  `/api/v1/watchlist/{id}`) with no `Authorization` header returns
  401/403; with a valid `Bearer <token>` (manually constructed via
  `create_session_jwt`), returns 200.
- Frontend: no test framework installed in this repo currently (confirmed
  during earlier research this session) — manual verification only:
  `npm run build`/`npm run lint` clean, then a real click-through of the
  Google sign-in flow if browser tooling is available this session,
  otherwise curl-level verification of the bearer-token mechanics (`token`
  present in `POST /auth/google`'s JSON response, a follow-up request with
  `-H "Authorization: Bearer <token>"` succeeding against a gated route)
  plus confirming `/auth/me` returns 401/403 with no header at all.
- Manual end-to-end against the live stack: sign in via the deployed
  frontend, confirm the Sidebar shows the real Google account, confirm
  Watchlist add/remove persists under the real user id (not
  `"default-user"`), confirm logout actually clears the session and
  redirects to `/login`, confirm a second, different Google account gets
  its own empty Watchlist (not shared with the first).
