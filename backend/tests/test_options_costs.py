from backend.core.models import Side
from backend.engine.execution.options_costs import calculate_options_costs


def test_sell_side_costs_are_positive():
    costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.SELL)
    assert costs > 0.0


def test_buy_side_costs_are_lower_than_sell_side_for_the_same_turnover():
    # STT applies to the sell/write side only, same convention the equity
    # model (calculate_indian_costs) already uses for intraday.
    buy_costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.BUY)
    sell_costs = calculate_options_costs(premium=45.0, quantity=250.0, side=Side.SELL)
    assert buy_costs < sell_costs
