from datetime import datetime, timezone

from backend.engine.session import is_past_square_off_time


def test_before_cutoff_is_false():
    # 15:14 IST == 09:44 UTC
    ts = datetime(2024, 1, 1, 9, 44, tzinfo=timezone.utc)
    assert is_past_square_off_time(ts) is False


def test_at_cutoff_is_true():
    # 15:15 IST == 09:45 UTC
    ts = datetime(2024, 1, 1, 9, 45, tzinfo=timezone.utc)
    assert is_past_square_off_time(ts) is True


def test_after_cutoff_is_true():
    # 15:16 IST == 09:46 UTC
    ts = datetime(2024, 1, 1, 9, 46, tzinfo=timezone.utc)
    assert is_past_square_off_time(ts) is True


def test_next_day_before_cutoff_is_false_again():
    ts = datetime(2024, 1, 2, 4, 0, tzinfo=timezone.utc)  # 09:30 IST
    assert is_past_square_off_time(ts) is False


def test_naive_timestamp_treated_as_utc():
    ts = datetime(2024, 1, 1, 9, 46)
    assert is_past_square_off_time(ts) is True
