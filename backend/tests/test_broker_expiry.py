from datetime import datetime, timezone

from backend.brokers.expiry import next_fixed_time_ist, ttl_seconds_until


def test_before_the_target_hour_rolls_to_today():
    # 2026-01-15 01:00 UTC = 06:30 IST
    now = datetime(2026, 1, 15, 1, 0, tzinfo=timezone.utc)
    result = next_fixed_time_ist(now, hour=15, minute=30)  # 15:30 IST
    assert result.astimezone(timezone(timedelta_ist())).hour == 15


def timedelta_ist():
    from datetime import timedelta

    return timedelta(hours=5, minutes=30)


def test_after_the_target_hour_rolls_to_tomorrow():
    # 2026-01-15 12:00 UTC = 17:30 IST, well past 03:30 IST
    now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    result = next_fixed_time_ist(now, hour=3, minute=30)
    result_ist = result.astimezone(timezone(timedelta_ist()))
    assert result_ist.date().isoformat() == "2026-01-16"
    assert (result_ist.hour, result_ist.minute) == (3, 30)


def test_ttl_is_always_positive():
    now = datetime(2026, 1, 15, 0, 29, 59, tzinfo=timezone.utc)  # 05:59:59 IST
    assert ttl_seconds_until(now, hour=6, minute=0) >= 1
