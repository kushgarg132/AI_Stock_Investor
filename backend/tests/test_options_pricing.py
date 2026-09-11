import pytest

from backend.options.pricing import black_scholes_put, estimate_margin, realized_volatility


def test_realized_volatility_of_constant_prices_is_zero():
    assert realized_volatility([100.0] * 21) == 0.0


def test_realized_volatility_is_positive_for_moving_prices():
    closes = [100.0, 102.0, 99.0, 101.0, 98.0, 103.0]
    assert realized_volatility(closes) > 0.0


def test_realized_volatility_returns_zero_for_fewer_than_two_closes():
    assert realized_volatility([100.0]) == 0.0
    assert realized_volatility([]) == 0.0


def test_black_scholes_put_deep_itm_worth_more_than_deep_otm():
    # Same spot/vol/expiry, ITM strike (2900) must price above OTM (2000).
    itm = black_scholes_put(spot=2800.0, strike=2900.0, days_to_expiry=30, iv=0.25)
    otm = black_scholes_put(spot=2800.0, strike=2000.0, days_to_expiry=30, iv=0.25)
    assert itm > otm > 0.0


def test_black_scholes_put_zero_time_to_expiry_returns_zero():
    assert black_scholes_put(spot=2800.0, strike=2800.0, days_to_expiry=0, iv=0.25) == 0.0


def test_black_scholes_put_zero_iv_returns_zero():
    assert black_scholes_put(spot=2800.0, strike=2800.0, days_to_expiry=30, iv=0.0) == 0.0


def test_estimate_margin_is_flat_percentage_of_notional():
    margin = estimate_margin(spot=2800.0, strike=2760.0, premium=45.0, lot_size=250)
    assert margin == pytest.approx(2760.0 * 250 * 0.15)
