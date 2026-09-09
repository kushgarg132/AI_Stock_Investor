"""BrokerAdapter over Angel One's SmartAPI -- verified 2026-09-09 directly
against the official Python SDK's source
(https://github.com/angel-one/smartapi-python/blob/main/SmartApi/smartConnect.py)
and its README's example payloads, not guessed. No live account exists to
test against for real, matching this codebase's posture for Kite/Upstox.
No SDK dependency: plain httpx calls. Every httpx call in this file's tests
is mocked; nothing here makes a real network request in tests.

This broker's connect flow is structurally different from Kite/Upstox: there
is no redirect/authorization-code step at all. The human supplies their
Angel One client code, account password, and a fresh 6-digit TOTP code (from
their own authenticator app) directly to loginByPassword every time they
connect. Only the app-level API key (`X-PrivateKey`) is a long-lived
credential worth storing -- client code, password, and TOTP are request-time
parameters this adapter never persists.

Real API surface used (root https://apiconnect.angelone.in):
- Login:   POST /rest/auth/angelbroking/user/v1/loginByPassword
  body {"clientcode", "password", "totp"} ->
  {"status": bool, "data": {"jwtToken", "refreshToken", "feedToken"}} on
  success, {"status": false, "message": "..."} on failure. Session lasts
  until midnight IST.
- Quote:   POST /rest/secure/angelbroking/market/v1/quote
  body {"mode": "FULL", "exchangeTokens": {"NSE": ["3045"]}} ->
  {"data": {"fetched": [{"tradingSymbol", "symbolToken", "ltp", "open",
  "high", "low", "close", "tradeVolume", ...}]}}.
- Candle:  POST /rest/secure/angelbroking/historical/v1/getCandleData
  body {"exchange", "symboltoken", "interval", "fromdate", "todate"} (dates
  "YYYY-MM-DD HH:MM") -> {"data": [[iso_timestamp, o, h, l, c, volume], ...]}.
  Interval is a documented enum; only ONE_MINUTE/ONE_DAY are verified here.
- Every authenticated call needs: Authorization: Bearer {jwtToken},
  X-PrivateKey: {api key}, X-UserType: USER, X-SourceID: WEB,
  Content-type: application/json (the SDK also sends X-ClientLocalIP/
  X-ClientPublicIP/X-MACAddress; Angel One's docs don't document them as
  required, and this adapter omits them rather than fabricate values).
- Instruments: NOT a live API call -- a static JSON dump, fetched live
  2026-09-09 from
  https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json
  (145,599 real rows at fetch time: {token, symbol, name, expiry, strike,
  lotsize, instrumenttype, exch_seg, tick_size}). Equity rows carry a
  "-EQ"-suffixed symbol (e.g. "RELIANCE-EQ"), stripped here to match this
  app's plain tradingsymbol convention.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from backend.brokers.expiry import next_fixed_time_ist
from backend.brokers.protocol import BrokerSessionState
from backend.components.shared.models import PriceCandle
from backend.instruments.models import Instrument

_ROOT = "https://apiconnect.angelone.in"
_LOGIN_URL = f"{_ROOT}/rest/auth/angelbroking/user/v1/loginByPassword"
_QUOTE_URL = f"{_ROOT}/rest/secure/angelbroking/market/v1/quote"
_CANDLE_URL = f"{_ROOT}/rest/secure/angelbroking/historical/v1/getCandleData"
_SCRIP_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

_INTERVAL_MAP = {"1m": "ONE_MINUTE", "1d": "ONE_DAY"}
_PERIOD_DAYS = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 182, "1y": 365, "2y": 730, "5y": 1825}


class AngelOneAdapter:
    def __init__(
        self, api_key: Optional[str], api_secret: Optional[str], redis, user_id: str,
    ) -> None:
        # api_secret is accepted for shape-compatibility with the other
        # adapters' constructors, but unused: Angel One's login needs a
        # client code, password, and fresh TOTP, none of which this app
        # stores (see module docstring).
        self._api_key = api_key
        self._redis = redis
        self._key = f"broker:{user_id}:angel_one:access_token"
        self._scrip_cache: Optional[dict] = None

    async def state(self) -> BrokerSessionState:
        if not self._api_key:
            return BrokerSessionState.UNCONFIGURED
        token = await self.get_access_token()
        return BrokerSessionState.ACTIVE if token else BrokerSessionState.NEEDS_LOGIN

    async def login_url(self) -> Optional[str]:
        return None  # credential submission, not a redirect

    def _headers(self, token: Optional[str] = None) -> dict:
        headers = {
            "Content-type": "application/json", "Accept": "application/json",
            "X-PrivateKey": self._api_key, "X-UserType": "USER", "X-SourceID": "WEB",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def connect(self, **fields: str) -> str:
        if not self._api_key:
            raise RuntimeError("Cannot connect to Angel One: API key is not configured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _LOGIN_URL,
                json={"clientcode": fields["client_code"], "password": fields["password"], "totp": fields["totp"]},
                headers=self._headers(),
            )
            resp.raise_for_status()

        body = resp.json()
        if not body.get("status"):
            raise RuntimeError(f"Angel One rejected the login: {body.get('message', 'unknown error')}")

        access_token = body["data"]["jwtToken"]
        now = datetime.now(timezone.utc)
        ttl = max(1, int((next_fixed_time_ist(now, hour=0, minute=0) - now).total_seconds()))
        await self._redis.set(self._key, access_token, ex=ttl)
        return access_token

    async def get_access_token(self) -> Optional[str]:
        return await self._redis.get(self._key)

    async def disconnect(self) -> None:
        await self._redis.delete(self._key)

    async def _load_scrip(self) -> dict:
        if self._scrip_cache is not None:
            return self._scrip_cache

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_SCRIP_URL)
            resp.raise_for_status()

        by_symbol = {}
        for row in resp.json():
            symbol = row["symbol"]
            plain = symbol[:-3] if symbol.endswith("-EQ") else symbol
            by_symbol[(row["exch_seg"], plain)] = row
        self._scrip_cache = by_symbol
        return by_symbol

    async def _resolve(self, instrument: Instrument) -> dict:
        scrip = await self._load_scrip()
        row = scrip.get((instrument.exchange, instrument.tradingsymbol))
        if row is None:
            raise ValueError(
                f"{instrument.tradingsymbol!r} not found in Angel One's {instrument.exchange} scrip master"
            )
        return row

    async def quote(self, instrument: Instrument) -> dict:
        row = await self._resolve(instrument)
        token = await self.get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _QUOTE_URL, json={"mode": "FULL", "exchangeTokens": {instrument.exchange: [row["token"]]}},
                headers=self._headers(token),
            )
            resp.raise_for_status()

        data = resp.json()["data"]["fetched"][0]
        return {
            "symbol": instrument.tradingsymbol,
            "last_price": data["ltp"],
            "open": data.get("open", data["ltp"]),
            "high": data.get("high", data["ltp"]),
            "low": data.get("low", data["ltp"]),
            "close": data.get("close", data["ltp"]),
            "volume": data.get("tradeVolume", 0),
        }

    async def history(self, instrument: Instrument, interval: str, period: str) -> list[PriceCandle]:
        try:
            angel_interval = _INTERVAL_MAP[interval]
        except KeyError:
            raise ValueError(
                f"Unsupported interval for Angel One: {interval!r}. Supported: {sorted(_INTERVAL_MAP)}"
            ) from None
        try:
            days = _PERIOD_DAYS[period]
        except KeyError:
            raise ValueError(f"Unsupported period for Angel One: {period!r}. Supported: {sorted(_PERIOD_DAYS)}") from None

        row = await self._resolve(instrument)
        token = await self.get_access_token()
        to_dt = datetime.now(timezone.utc)
        from_dt = to_dt - timedelta(days=days)

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_CANDLE_URL, headers=self._headers(token), json={
                "exchange": instrument.exchange, "symboltoken": row["token"], "interval": angel_interval,
                "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"), "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
            })
            resp.raise_for_status()

        candles = resp.json()["data"]
        return [
            PriceCandle(
                symbol=instrument.tradingsymbol, timestamp=c[0], open=c[1], high=c[2],
                low=c[3], close=c[4], adj_close=c[4], volume=c[5],
            )
            for c in candles
        ]

    async def instruments(self, exchanges: tuple[str, ...] = ("NSE",)) -> list[Instrument]:
        scrip = await self._load_scrip()
        result = []
        for (exch_seg, symbol), row in scrip.items():
            if exch_seg not in exchanges:
                continue
            try:
                token = int(row["token"])
                lot_size = int(float(row["lotsize"]))
                tick_size = float(row["tick_size"])
            except (KeyError, ValueError):
                continue
            result.append(Instrument(
                exchange=exch_seg, tradingsymbol=symbol, name=row["name"], instrument_token=token,
                exchange_token=token, instrument_type=row.get("instrumenttype") or "EQ", segment=exch_seg,
                lot_size=lot_size, tick_size=tick_size,
            ))
        return result

    async def ticker_feed(self, instrument_tokens, timeframe, timeframe_seconds):
        # Angel One's WebSocket feed exists but isn't wired in this pass --
        # callers fall back to polling, same as no broker connected at all.
        return None
