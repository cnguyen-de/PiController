import datetime

from fan_controller.config import Config
from fan_controller.modes import Mode, cycle_on, decide

COLD = 40.0
WARM = 51.0  # between the two thermal thresholds
HOT = 60.0


def on_phase(hour):
    """A time in the given hour falling in the duty cycle's 'on' half."""
    return _phase(hour, want_on=True)


def off_phase(hour):
    """A time in the given hour falling in the duty cycle's 'off' half."""
    return _phase(hour, want_on=False)


def _phase(hour, want_on):
    # :00 and :05 are adjacent 300s blocks, so they are always opposite phases.
    for minute in (0, 5):
        when = datetime.datetime(2026, 8, 25, hour, minute)
        if cycle_on(when) is want_on:
            return when
    raise AssertionError("no matching cycle phase found")


class TestVacation:
    def test_fan_runs_even_in_the_cycle_off_phase(self):
        assert decide(Mode.VACATION, off_phase(14), COLD, False).fan_on is True

    def test_fan_runs_through_the_night(self):
        assert decide(Mode.VACATION, off_phase(3), COLD, False).fan_on is True


class TestNormal:
    def test_follows_the_cycle_during_the_day(self):
        assert decide(Mode.NORMAL, on_phase(14), COLD, False).fan_on is True
        assert decide(Mode.NORMAL, off_phase(14), COLD, False).fan_on is False

    def test_keeps_cycling_overnight_because_normal_has_no_quiet_hours(self):
        assert decide(Mode.NORMAL, on_phase(3), COLD, False).fan_on is True
        assert decide(Mode.NORMAL, off_phase(3), COLD, False).fan_on is False


class TestGuest:
    def test_follows_the_cycle_during_the_day(self):
        assert decide(Mode.GUEST, on_phase(14), COLD, False).fan_on is True
        assert decide(Mode.GUEST, off_phase(14), COLD, False).fan_on is False

    def test_stays_silent_in_the_quiet_window_even_in_the_cycle_on_phase(self):
        assert decide(Mode.GUEST, on_phase(22), COLD, False).fan_on is False
        assert decide(Mode.GUEST, on_phase(3), COLD, False).fan_on is False

    def test_resumes_cycling_when_the_quiet_window_ends(self):
        assert decide(Mode.GUEST, on_phase(8), COLD, False).fan_on is True


class TestThermalOverride:
    def test_heat_starts_the_fan_in_the_cycle_off_phase(self):
        assert decide(Mode.NORMAL, off_phase(14), HOT, False).fan_on is True

    def test_heat_beats_guest_quiet_hours(self):
        assert decide(Mode.GUEST, off_phase(3), HOT, False).fan_on is True

    def test_crossing_the_upper_threshold_latches_thermal_demand(self):
        assert decide(Mode.NORMAL, off_phase(14), 55.0, False).thermal_latched is True

    def test_latched_demand_holds_between_the_thresholds(self):
        result = decide(Mode.GUEST, off_phase(3), WARM, True)
        assert result.thermal_latched is True
        assert result.fan_on is True

    def test_unlatched_demand_stays_off_between_the_thresholds(self):
        result = decide(Mode.GUEST, off_phase(3), WARM, False)
        assert result.thermal_latched is False
        assert result.fan_on is False

    def test_falling_to_the_lower_threshold_releases_the_latch(self):
        result = decide(Mode.GUEST, off_phase(3), 48.0, True)
        assert result.thermal_latched is False
        assert result.fan_on is False

    def test_releasing_the_latch_returns_control_to_the_mode(self):
        result = decide(Mode.NORMAL, on_phase(14), COLD, True)
        assert result.thermal_latched is False
        assert result.fan_on is True


class TestConfigurable:
    def test_thermal_thresholds_come_from_config(self):
        config = Config(thermal_on_c=70.0, thermal_off_c=65.0)

        assert decide(Mode.NORMAL, off_phase(14), HOT, False, config).fan_on is False
        assert decide(Mode.NORMAL, off_phase(14), 71.0, False, config).fan_on is True

    def test_the_guest_quiet_window_comes_from_config(self):
        config = Config(guest_quiet_start=datetime.time(23, 0),
                        guest_quiet_end=datetime.time(6, 0))

        # 22:00 is inside the default window but outside this one.
        assert decide(Mode.GUEST, on_phase(22), COLD, False, config).fan_on is True
        assert decide(Mode.GUEST, on_phase(23), COLD, False, config).fan_on is False

    def test_the_cycle_length_comes_from_config(self):
        ten_minutes = Config(cycle_seconds=600)

        # Same instant, opposite phase, because the window is twice as long.
        when = datetime.datetime.fromtimestamp(300, tz=datetime.timezone.utc)
        assert cycle_on(when) is False
        assert cycle_on(when, ten_minutes.cycle_seconds) is True
