"""allocate_core_satellite: pure split arithmetic + edge cases."""

import pytest

from backend.screening.allocation import allocate_core_satellite


def test_standard_70_30_split_equal_weighted_within_each_sleeve():
    result = allocate_core_satellite(
        total_capital=100_000.0,
        core_symbols=["NIFTYBEES", "JUNIORBEES"],
        satellite_symbols=["A", "B", "C"],
        core_weight=0.7,
    )

    assert result["NIFTYBEES"] == pytest.approx(35_000.0)
    assert result["JUNIORBEES"] == pytest.approx(35_000.0)
    assert result["A"] == pytest.approx(10_000.0)
    assert result["B"] == pytest.approx(10_000.0)
    assert result["C"] == pytest.approx(10_000.0)
    assert sum(result.values()) == pytest.approx(100_000.0)


def test_empty_satellite_list_puts_everything_in_core():
    result = allocate_core_satellite(
        total_capital=50_000.0, core_symbols=["NIFTYBEES"], satellite_symbols=[],
    )
    assert result == {"NIFTYBEES": pytest.approx(50_000.0)}


def test_empty_core_list_puts_everything_in_satellite():
    result = allocate_core_satellite(
        total_capital=50_000.0, core_symbols=[], satellite_symbols=["A", "B"],
    )
    assert result["A"] == pytest.approx(25_000.0)
    assert result["B"] == pytest.approx(25_000.0)


def test_both_empty_raises():
    with pytest.raises(ValueError):
        allocate_core_satellite(total_capital=50_000.0, core_symbols=[], satellite_symbols=[])


def test_invalid_core_weight_raises():
    with pytest.raises(ValueError):
        allocate_core_satellite(
            total_capital=100.0, core_symbols=["A"], satellite_symbols=["B"], core_weight=1.5,
        )
