"""Intent is the structural guard behind "no rule hit, no intent": it must
be impossible to construct one without a reason and a valid strength."""

from dataclasses import FrozenInstanceError

import pytest

from backend.core.models import Intent, Order, Side


def test_intent_rejects_empty_reason_codes():
    with pytest.raises(ValueError):
        Intent(symbol="TEST", side=Side.BUY, strength=0.5, reason_codes=[])


@pytest.mark.parametrize("strength", [-0.01, 1.01, -5.0, 5.0])
def test_intent_rejects_out_of_range_strength(strength):
    with pytest.raises(ValueError):
        Intent(symbol="TEST", side=Side.BUY, strength=strength, reason_codes=["r"])


def test_intent_accepts_valid_boundary_values():
    for strength in (0.0, 1.0, 0.5):
        intent = Intent(symbol="TEST", side=Side.BUY, strength=strength, reason_codes=["r"])
        assert intent.side == Side.BUY
        assert intent.side.value == "BUY"


def test_intent_is_frozen():
    intent = Intent(symbol="TEST", side=Side.SELL, strength=0.5, reason_codes=["r"])
    with pytest.raises(FrozenInstanceError):
        intent.strength = 0.9  # type: ignore[misc]


def _order(quantity: float) -> Order:
    return Order(id="x", symbol="RELIANCE", side=Side.BUY, quantity=quantity, order_type="MARKET")


def test_whole_quantity_returns_int_for_a_whole_share_count():
    assert _order(10.0).whole_quantity() == 10


def test_whole_quantity_rejects_a_fractional_share_count():
    with pytest.raises(ValueError):
        _order(10.5).whole_quantity()
