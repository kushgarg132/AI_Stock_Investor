from backend.risk.kill_switch import should_trip


def test_a_loss_at_the_limit_trips():
    assert should_trip(equity=-50000.0, daily_loss_limit=50000.0) is True


def test_a_loss_short_of_the_limit_does_not_trip():
    assert should_trip(equity=-49999.0, daily_loss_limit=50000.0) is False


def test_a_profit_never_trips():
    assert should_trip(equity=100000.0, daily_loss_limit=50000.0) is False


def test_zero_equity_does_not_trip():
    assert should_trip(equity=0.0, daily_loss_limit=50000.0) is False
