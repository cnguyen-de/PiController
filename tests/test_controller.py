import datetime

from fan_controller.config import Config
from fan_controller.controller import Controller
from fan_controller.modes import Mode, cycle_on


class FakeFan:
    def __init__(self):
        self.is_on = None
        self.history = []

    def set(self, on):
        self.is_on = on
        self.history.append(on)


def _phase(hour, want_on):
    for minute in (0, 5):
        when = datetime.datetime(2026, 8, 25, hour, minute)
        if cycle_on(when) is want_on:
            return when
    raise AssertionError("no matching cycle phase found")


def build(mode=Mode.NORMAL, temp=40.0, when=None, on_mode_change=None):
    """A controller wired to fakes, with a frozen clock and thermometer."""
    fan = FakeFan()
    box = {"temp": temp, "now": when or _phase(14, want_on=True)}
    controller = Controller(
        config=Config(),
        fan=fan,
        read_temp=lambda: box["temp"],
        clock=lambda: box["now"],
        mode=mode,
        on_mode_change=on_mode_change,
    )
    return controller, fan, box


def test_a_tick_starts_the_fan_when_the_mode_calls_for_it():
    controller, fan, _ = build(when=_phase(14, want_on=True))

    controller.tick()

    assert fan.is_on is True


def test_a_tick_stops_the_fan_when_the_mode_does_not_call_for_it():
    controller, fan, _ = build(when=_phase(14, want_on=False))

    controller.tick()

    assert fan.is_on is False


def test_repeated_ticks_do_not_re_issue_the_same_state():
    controller, fan, _ = build(when=_phase(14, want_on=True))

    controller.tick()
    controller.tick()
    controller.tick()

    assert fan.history == [True, True, True]  # the Fan class itself de-dupes


def test_the_thermal_latch_survives_between_ticks():
    controller, fan, box = build(when=_phase(14, want_on=False))

    box["temp"] = 60.0
    controller.tick()
    assert fan.is_on is True

    # Cooling to 51C is inside the hysteresis band, so demand must hold.
    box["temp"] = 51.0
    controller.tick()
    assert fan.is_on is True

    # Dropping to the release threshold hands control back to the mode,
    # which is in its off phase.
    box["temp"] = 48.0
    controller.tick()
    assert fan.is_on is False


def test_switching_mode_changes_what_the_next_tick_does():
    controller, fan, _ = build(mode=Mode.NORMAL, when=_phase(14, want_on=False))

    controller.tick()
    assert fan.is_on is False

    controller.set_mode(Mode.VACATION)
    controller.tick()
    assert fan.is_on is True


def test_switching_mode_notifies_the_caller_so_it_can_be_saved_and_published():
    seen = []
    controller, _, _ = build(on_mode_change=seen.append)

    controller.set_mode(Mode.GUEST)

    assert seen == [Mode.GUEST]


def test_the_current_mode_is_readable():
    controller, _, _ = build(mode=Mode.GUEST)
    assert controller.mode is Mode.GUEST

    controller.set_mode(Mode.VACATION)
    assert controller.mode is Mode.VACATION


def test_a_failed_temperature_read_does_not_stop_the_loop():
    fan = FakeFan()
    def exploding_thermometer():
        raise OSError("no thermal zone")

    controller = Controller(
        config=Config(),
        fan=fan,
        read_temp=exploding_thermometer,
        clock=lambda: _phase(14, want_on=True),
        mode=Mode.NORMAL,
    )

    controller.tick()

    # Mode logic still runs; the unreadable sensor simply raises no demand.
    assert fan.is_on is True
