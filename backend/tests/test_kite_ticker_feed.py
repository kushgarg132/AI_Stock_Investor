"""KiteTickerFeed: synthetic on_ticks calls -> correct 1-minute bar
aggregation, closing on the clock (not on next-tick arrival) so a quiet
symbol still emits a flat bar. Drives a fake clock/sleep -- no real
WebSocket, no real timing wait. `KiteTicker` itself is never imported here;
`kite_ticker_factory` returns a bare MagicMock standing in for it."""

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.data.feeds.live_kite import KiteTickerFeed


class _FakeClock:
    """now()/sleep() pair that advance together: awaiting sleep(n) moves the
    fake clock forward by n seconds without any real wall-clock wait. The
    `asyncio.sleep(0)` checkpoint is still real -- it just hands control
    back to the event loop for one tick rather than actually waiting, which
    keeps this a genuine coroutine (so a caller stuck forever with no ticks,
    per test_no_bar_before_any_tick_ever_seen below, can still be cancelled)
    instead of a synchronous busy-spin."""

    def __init__(self, start: float = 0.0):
        self.t = start

    def now(self) -> float:
        return self.t

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(0)
        self.t += seconds


def _tick(token, price, volume_traded=None):
    tick = {"instrument_token": token, "last_price": price}
    if volume_traded is not None:
        tick["volume_traded"] = volume_traded
    return tick


def _make_feed(clock, **kwargs):
    return KiteTickerFeed(
        kite_ticker_factory=lambda: MagicMock(),
        instrument_tokens=[1],
        timeframe_seconds=60.0,
        tick_check_seconds=60.0,
        now_fn=clock.now,
        sleep_fn=clock.sleep,
        **kwargs,
    )


async def test_on_connect_subscribes_and_sets_full_mode():
    mock_ws = MagicMock()
    mock_ws.MODE_FULL = "full"
    feed = KiteTickerFeed(kite_ticker_factory=lambda: mock_ws, instrument_tokens=[1, 2])

    feed.on_connect(mock_ws, {"some": "response"})

    mock_ws.subscribe.assert_called_once_with([1, 2])
    mock_ws.set_mode.assert_called_once_with("full", [1, 2])


async def test_bar_emitted_on_clock_tick_with_correct_ohlcv():
    clock = _FakeClock()
    feed = _make_feed(clock)
    gen = feed.__aiter__()

    feed.on_ticks(MagicMock(), [_tick(1, 100.0, volume_traded=1000)])
    await asyncio.sleep(0)  # let the call_soon_threadsafe-scheduled ingest run

    bar1 = await gen.__anext__()  # clock advances 0 -> 60, window [0,60) flushes
    assert (bar1.open, bar1.high, bar1.low, bar1.close) == (100.0, 100.0, 100.0, 100.0)
    assert bar1.volume == 0.0  # no prior cumulative-volume baseline for the first bar
    assert bar1.instrument_token == 1


async def test_second_window_computes_true_ohlc_and_volume_delta():
    clock = _FakeClock()
    feed = _make_feed(clock)
    gen = feed.__aiter__()

    feed.on_ticks(MagicMock(), [_tick(1, 100.0, volume_traded=1000)])
    await asyncio.sleep(0)
    await gen.__anext__()  # bar1, establishes volume baseline of 1000

    feed.on_ticks(MagicMock(), [_tick(1, 105.0, volume_traded=1300)])
    feed.on_ticks(MagicMock(), [_tick(1, 102.0, volume_traded=1450)])
    await asyncio.sleep(0)

    bar2 = await gen.__anext__()  # window [60,120) flushes
    assert bar2.open == 105.0  # first tick of the window, NOT the carried-over close
    assert bar2.high == 105.0
    assert bar2.low == 102.0
    assert bar2.close == 102.0
    assert bar2.volume == 450.0  # 1450 - 1000


async def test_quiet_window_still_emits_flat_bar_at_last_close():
    clock = _FakeClock()
    feed = _make_feed(clock)
    gen = feed.__aiter__()

    feed.on_ticks(MagicMock(), [_tick(1, 100.0, volume_traded=1000)])
    await asyncio.sleep(0)
    await gen.__anext__()  # bar1 @ [0,60)

    feed.on_ticks(MagicMock(), [_tick(1, 102.0, volume_traded=1450)])
    await asyncio.sleep(0)
    await gen.__anext__()  # bar2 @ [60,120)

    # No ticks at all during [120,180) -- window must still flush.
    bar3 = await gen.__anext__()
    assert (bar3.open, bar3.high, bar3.low, bar3.close) == (102.0, 102.0, 102.0, 102.0)
    assert bar3.volume == 0.0


async def test_no_bar_before_any_tick_ever_seen():
    clock = _FakeClock()
    feed = _make_feed(clock)
    gen = feed.__aiter__()

    # Nothing ticked yet -- flushing must not fabricate a bar out of nothing,
    # so __anext__() should never resolve; a short real-time timeout proves
    # it (the fake clock's own time never gates this, only real ticks do).
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(gen.__anext__(), timeout=0.05)
