"""BrokerAdapter over Upstox's v2 REST API -- verified 2026-09-09 against
https://upstox.com/developer/api-documentation (fetched live; no Upstox
account exists to test against for real, matching this codebase's existing
posture for Kite -- see backend/auth/kite_session.py's own docstring).

No SDK: plain httpx calls, following the pattern the settings router already
uses for the OmniRoute gateway.

Real API surface used:
- Authorize:  GET https://api.upstox.com/v2/login/authorization/dialog
  (response_type=code, client_id, redirect_uri, state) -- a redirect the
  human completes; Upstox returns a single-use `code`.
- Token:      POST https://api.upstox.com/v2/login/authorization/token,
  application/x-www-form-urlencoded, fields code/client_id/client_secret/
  redirect_uri/grant_type=authorization_code -> {"access_token": ...}.
  Valid until 3:30 AM IST the following day regardless of issue time.
- Quote:      GET https://api.upstox.com/v2/market-quote/quotes
  ?instrument_key=... , Bearer auth -> {"data": {key: {"last_price",
  "ohlc": {open,high,low,close}, "volume", ...}}}.
- Historical: GET https://api.upstox.com/v2/historical-candle/
  {instrument_key}/{interval}/{to_date}/{from_date}, dates as YYYY-MM-DD ->
  {"data": {"candles": [[iso_timestamp, open, high, low, close, volume, oi], ...]}}.
  Interval is a documented enum; only 1minute/30minute/day are verified here
  -- everything else raises rather than guessing.
- Instruments: NOT a live API call. A gzip-compressed JSON dump per exchange
  at https://assets.upstox.com/market-quote/instruments/exchange/{EXCH}.json.gz,
  refreshed daily, each row carrying instrument_key (the real query key --
  segment|ISIN, NOT the numeric exchange_token), trading_symbol,
  exchange_token, lot_size, tick_size.

Because instrument_key (Upstox's actual query key) isn't ISIN data the
shared Instrument model carries from other brokers' sources, quote()/
history() resolve it themselves from this adapter's own cached scrip-master
lookup, keyed by tradingsymbol -- not from the Instrument object's
instrument_token, which here is Upstox's exchange_token (numeric, but not
the key Upstox's REST API actually accepts).
"""

import gzip
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from backend.brokers.expiry import ttl_seconds_until
from backend.brokers.protocol import BrokerSessionState
from backend.components.shared.models import PriceCandle
from backend.instruments.models import Instrument

_AUTHORIZE_URL = "https://api.upstox.com/v2/login/authorization/dialog"
_TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
_QUOTE_URL = "https://api.upstox.com/v2/market-quote/quotes"
_HISTORY_URL = "https://api.upstox.com/v2/historical-candle/{key}/{interval}/{to_date}/{from_date}"
_SCRIP_URL = "https://assets.upstox.com/market-quote/instruments/exchange/{exchange}.json.gz"

_INTERVAL_MAP = {"1m": "1minute", "30m": "30minute", "1d": "day"}
_PERIOD_DAYS = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 182, "1y": 365, "2y": 730, "5y": 1825}


class UpstoxAdapter:
    def __init__(
        self, api_key: Optional[str], api_secret: Optional[str], redirect_uri: Optional[str],
        redis, user_id: str,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._redirect_uri = redirect_uri
        self._redis = redis
        self._key = f"broker:{user_id}:upstox:access_token"
        self._scrip_cache: dict[str, dict[tuple, dict]] = {}

    async def state(self) -> BrokerSessionState:
        if not self._api_key or not self._api_secret:
            return BrokerSessionState.UNCONFIGURED
        token = await self.get_access_token()
        return BrokerSessionState.ACTIVE if token else BrokerSessionState.NEEDS_LOGIN

    async def login_url(self) -> Optional[str]:
        if not self._api_key:
            raise RuntimeError("Cannot generate Upstox login URL: client id is not configured")
        return str(httpx.URL(_AUTHORIZE_URL, params={
            "response_type": "code", "client_id": self._api_key, "redirect_uri": self._redirect_uri,
        }))

    async def connect(self, **fields: str) -> str:
        if not self._api_key or not self._api_secret:
            raise RuntimeError("Cannot connect to Upstox: client id/secret not configured")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(_TOKEN_URL, data={
                "code": fields["request_token"], "client_id": self._api_key,
                "client_secret": self._api_secret, "redirect_uri": self._redirect_uri,
                "grant_type": "authorization_code",
            })
            resp.raise_for_status()

        access_token = resp.json()["access_token"]
        now = datetime.now(timezone.utc)
        await self._redis.set(self._key, access_token, ex=ttl_seconds_until(now, hour=3, minute=30))
        return access_token

    async def get_access_token(self) -> Optional[str]:
        return await self._redis.get(self._key)

    async def disconnect(self) -> None:
        await self._redis.delete(self._key)

    async def _load_scrip(self, exchange: str) -> dict:
        if exchange in self._scrip_cache:
            return self._scrip_cache[exchange]

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(_SCRIP_URL.format(exchange=exchange))
            resp.raise_for_status()

        rows = json.loads(gzip.decompress(resp.content))
        by_symbol = {row["trading_symbol"]: row for row in rows}
        self._scrip_cache[exchange] = by_symbol
        return by_symbol

    async def _resolve(self, instrument: Instrument) -> dict:
        scrip = await self._load_scrip(instrument.exchange)
        row = scrip.get(instrument.tradingsymbol)
        if row is None:
            raise ValueError(
                f"{instrument.tradingsymbol!r} not found in Upstox's {instrument.exchange} instrument dump"
            )
        return row

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async def quote(self, instrument: Instrument) -> dict:
        row = await self._resolve(instrument)
        token = await self.get_access_token()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _QUOTE_URL, params={"instrument_key": row["instrument_key"]}, headers=self._headers(token),
            )
            resp.raise_for_status()

        data = next(iter(resp.json()["data"].values()))
        ohlc = data.get("ohlc", {})
        return {
            "symbol": instrument.tradingsymbol,
            "last_price": data["last_price"],
            "open": ohlc.get("open", data["last_price"]),
            "high": ohlc.get("high", data["last_price"]),
            "low": ohlc.get("low", data["last_price"]),
            "close": ohlc.get("close", data["last_price"]),
            "volume": data.get("volume", 0),
        }

    async def history(self, instrument: Instrument, interval: str, period: str) -> list[PriceCandle]:
        try:
            upstox_interval = _INTERVAL_MAP[interval]
        except KeyError:
            raise ValueError(
                f"Unsupported interval for Upstox: {interval!r}. Supported: {sorted(_INTERVAL_MAP)}"
            ) from None
        try:
            days = _PERIOD_DAYS[period]
        except KeyError:
            raise ValueError(f"Unsupported period for Upstox: {period!r}. Supported: {sorted(_PERIOD_DAYS)}") from None

        row = await self._resolve(instrument)
        token = await self.get_access_token()
        to_date = datetime.now(timezone.utc).date()
        from_date = to_date - timedelta(days=days)

        url = _HISTORY_URL.format(
            key=row["instrument_key"], interval=upstox_interval,
            to_date=to_date.isoformat(), from_date=from_date.isoformat(),
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers(token))
            resp.raise_for_status()

        candles = resp.json()["data"]["candles"]
        return [
            PriceCandle(
                symbol=instrument.tradingsymbol, timestamp=c[0], open=c[1], high=c[2],
                low=c[3], close=c[4], adj_close=c[4], volume=c[5],
            )
            for c in candles
        ]

    async def instruments(self, exchanges: tuple[str, ...] = ("NSE",)) -> list[Instrument]:
        result = []
        for exchange in exchanges:
            scrip = await self._load_scrip(exchange)
            for row in scrip.values():
                result.append(Instrument(
                    exchange=row["exchange"], tradingsymbol=row["trading_symbol"], name=row["name"],
                    instrument_token=int(row["exchange_token"]), exchange_token=int(row["exchange_token"]),
                    instrument_type=row["instrument_type"], segment=row["segment"],
                    lot_size=int(row["lot_size"]), tick_size=float(row["tick_size"]),
                    isin=row.get("isin"),
                ))
        return result

    async def ticker_feed(self, instrument_tokens, timeframe, timeframe_seconds):
        # Upstox does offer a WebSocket feed, but wiring its (protobuf-framed)
        # binary protocol is out of scope for this pass -- callers fall back
        # to polling, exactly as when no broker is connected at all.
        return None
