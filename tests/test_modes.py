import datetime

import pytest

from fan_controller.modes import cycle_on, in_quiet_window


def at(epoch_seconds):
    return datetime.datetime.fromtimestamp(epoch_seconds, tz=datetime.timezone.utc)


def clock(hour, minute=0):
    return datetime.datetime(2026, 8, 25, hour, minute)


def test_cycle_is_on_during_the_first_five_minutes_of_a_ten_minute_window():
    assert cycle_on(at(0)) is True
    assert cycle_on(at(299)) is True


def test_cycle_is_off_during_the_second_five_minutes():
    assert cycle_on(at(300)) is False
    assert cycle_on(at(599)) is False


def test_cycle_flips_back_on_at_the_next_boundary():
    assert cycle_on(at(600)) is True


@pytest.mark.parametrize("hour", [21, 22, 0, 3, 7])
def test_quiet_window_spans_midnight_from_nine_pm_to_eight_am(hour):
    assert in_quiet_window(clock(hour)) is True


@pytest.mark.parametrize("hour", [8, 12, 17, 20])
def test_quiet_window_excludes_the_daytime(hour):
    assert in_quiet_window(clock(hour)) is False


def test_quiet_window_boundaries_are_inclusive_at_start_exclusive_at_end():
    assert in_quiet_window(clock(20, 59)) is False
    assert in_quiet_window(clock(21, 0)) is True
    assert in_quiet_window(clock(7, 59)) is True
    assert in_quiet_window(clock(8, 0)) is False
