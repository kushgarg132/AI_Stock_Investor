"""DataFeed backed by `kiteconnect.KiteTicker`, Kite Connect's WebSocket
streaming API (https://kite.trade/docs/connect/v3/websocket/). **Not
instantiated or run by anything in this task** -- no live Kite
account/access_token exists in this session, so this class only needs to
exist correctly (verified against the real pykiteconnect 5.2.1 source,
cited inline below) plus pass unit tests that feed it synthetic ticks
through mocked callbacks. `backend.data.feeds.polling_live.PollingLiveFeed`
is what actually runs today; swapping it for this class later is a one-line
change since both implement the same `DataFeed` protocol.

Real API surface this wraps:
- `KiteTicker(api_key, access_token, reconnect=True)` -- `reconnect=True` is
  the SDK's own documented default; this class relies on it rather than
  reimplementing reconnect/backoff.
- `kws.on_ticks = fn` / `kws.on_connect = fn` -- plain callback attributes
  (not registration methods) the SDK invokes: `on_ticks(ws, ticks)` with
  `ticks` a list of dicts (each carrying at least `instrument_token`,
  `last_price`, and, in full mode, `ohlc` + `volume_traded`, per
  `ticker.py::_parse_binary`), `on_connect(ws, response)`.
- `kws.subscribe(tokens)` then `kws.set_mode(KiteTicker.MODE_FULL, tokens)`
  -- full mode is what carries `ohlc`/`volume_traded`, needed for real
  OHLCV bars rather than LTP-only ticks.
- `kws.connect(threaded=True)` -- runs Kite's Twisted-based WebSocket client
  on a background thread and returns immediately; without `threaded=True`
  it blocks the calling thread forever running the reactor. Ticks therefore
  arrive on a thread that is NOT the asyncio event loop's thread -- this
  class hands them over via `loop.call_soon_threadsafe`, never touching
  asyncio state directly from the callback.

Bar aggregation is deliberately clock-driven, not tick-driven: a periodic
flush (`sleep_fn`-paced, default `asyncio.sleep`) closes each instrument's
current window at its clock boundary regardless of whether a new tick has
arrived, so a quiet symbol still emits a bar (using its last known price,
flat, zero volume) instead of silently never producing one. `now_fn`/
`sleep_fn` are injectable so tests can drive this without any real wall-clock
waiting.
"""

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Optional

from backend.core.models import Bar


class _Window:
    """One instrument's in-progress bar. `open`/`high`/`low`/`close` stay
    None until a real tick lands in this window; `volume_last` tracks Kite's
    cumulative `volume_traded` (NOT a per-tick volume) so the flush step can
    compute a true delta against the previous window's final reading.
    """

    __slots__ = ("window_start", "open", "high", "low", "close", "volume_last")

    def __init__(self, window_start: float) -> None:
        self.window_start = window_start
        self.open: Optional[float] = None
        self.high: Optional[float] = None
        self.low: Optional[float] = None
        self.close: Optional[float] = None
        self.volume_last: Optional[float] = None

    def update(self, tick: dict) -> None:
        price = tick["last_price"]
        if self.open is None:
            self.open = price
        self.high = price if self.high is None else max(self.high, price)
        self.low = price if self.low is None else min(self.low, price)
        self.close = price
        volume_traded = tick.get("volume_traded")
        if volume_traded is not None:
            self.volume_last = volume_traded


class KiteTickerFeed:
    def __init__(
        self,
        kite_ticker_factory: Callable[[], "KiteTicker"],  # noqa: F821
        instrument_tokens: list[int],
        timeframe: str = "1m",
        timeframe_seconds: float = 60.0,
        tick_check_seconds: float = 1.0,
        now_fn: Callable[[], float] = None,
        sleep_fn: Callable[[float], "asyncio.Future"] = asyncio.sleep,
    ) -> None:
        self._kite_ticker_factory = kite_ticker_factory
        self._tokens = instrument_tokens
        self._timeframe = timeframe
        self._timeframe_seconds = timeframe_seconds
        self._tick_check_seconds = tick_check_seconds
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc).timestamp())
        self._sleep_fn = sleep_fn

        self._windows: dict[int, _Window] = {}
        self._last_close: dict[int, float] = {}
        self._last_cum_volume: dict[int, float] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # -- SDK callbacks (invoked on the Twisted reactor thread in production,
    # or called directly by tests) --

    def on_ticks(self, ws, ticks: list[dict]) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._ingest, ticks)
        else:
            self._ingest(ticks)

    def on_connect(self, ws, response) -> None:
        ws.subscribe(self._tokens)
        ws.set_mode(ws.MODE_FULL, self._tokens)

    def _ingest(self, ticks: list[dict]) -> None:
        now = self._now_fn()
        for tick in ticks:
            token = tick["instrument_token"]
            window = self._windows.get(token)
            if window is None:
                window_start = now - (now % self._timeframe_seconds)
                window = self._windows[token] = _Window(window_start)
            window.update(tick)

    def _flush_due_windows(self, now: float) -> list:
        bars = []
        for token in set(self._windows.keys()) | set(self._last_close.keys()):
            window = self._windows.get(token)
            window_start = window.window_start if window is not None else None
            if window_start is None or now < window_start + self._timeframe_seconds:
                continue

            if window is not None and window.close is not None:
                volume = 0.0
                if window.volume_last is not None:
                    baseline = self._last_cum_volume.get(token)
                    volume = max(0.0, window.volume_last - baseline) if baseline is not None else 0.0
                    self._last_cum_volume[token] = window.volume_last
                bar = Bar(
                    instrument_token=token,
                    timeframe=self._timeframe,
                    timestamp=datetime.fromtimestamp(window.window_start, tz=timezone.utc),
                    open=window.open,
                    high=window.high,
                    low=window.low,
                    close=window.close,
                    volume=volume,
                )
                self._last_close[token] = window.close
            else:
                last_close = self._last_close.get(token)
                if last_close is None:
                    self._windows.pop(token, None)
                    continue
                bar = Bar(
                    instrument_token=token,
                    timeframe=self._timeframe,
                    timestamp=datetime.fromtimestamp(window_start, tz=timezone.utc),
                    open=last_close,
                    high=last_close,
                    low=last_close,
                    close=last_close,
                    volume=0.0,
                )

            next_start = window_start + self._timeframe_seconds
            self._windows[token] = _Window(next_start)
            bars.append((window_start, bar))

        bars.sort(key=lambda pair: pair[0])
        return [bar for _, bar in bars]

    async def __aiter__(self) -> AsyncIterator[Bar]:
        self._loop = asyncio.get_running_loop()
        kws = self._kite_ticker_factory()
        kws.on_ticks = self.on_ticks
        kws.on_connect = self.on_connect
        kws.connect(threaded=True)  # non-blocking: runs the SDK's Twisted reactor on its own thread
        try:
            while True:
                await self._sleep_fn(self._tick_check_seconds)
                for bar in self._flush_due_windows(self._now_fn()):
                    yield bar
        finally:
            kws.close()
