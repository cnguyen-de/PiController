"""Pure fan-control decision logic. No I/O, no hardware, no clock of its own."""

import enum
from typing import NamedTuple

from .config import Config

DEFAULTS = Config()


class Mode(enum.Enum):
    GUEST = "guest"
    NORMAL = "normal"
    VACATION = "vacation"


class Decision(NamedTuple):
    fan_on: bool
    thermal_latched: bool


def cycle_on(now, cycle_seconds=DEFAULTS.cycle_seconds):
    """True during the 'on' half of the duty cycle.

    Phase comes from the wall clock rather than an internal timer, so bursts
    align to cycle boundaries of the epoch, cannot drift, and need no state
    restored after a restart.
    """
    return (int(now.timestamp()) // cycle_seconds) % 2 == 0


def in_quiet_window(now, start=DEFAULTS.guest_quiet_start,
                    end=DEFAULTS.guest_quiet_end):
    """True inside the guest-mode quiet window, which wraps past midnight."""
    return now.time() >= start or now.time() < end


def decide(mode, now, temp, thermal_latched, config=DEFAULTS):
    """Whether the fan should be running, and the new thermal latch state.

    The latch is passed in and handed back rather than held in a global, which
    keeps this function pure: the same arguments always give the same answer.
    """
    if temp >= config.thermal_on_c:
        thermal = True
    elif temp <= config.thermal_off_c:
        thermal = False
    else:
        thermal = thermal_latched

    # Heat outranks everything, including guest mode's quiet hours.
    if thermal:
        return Decision(True, thermal)
    if mode is Mode.VACATION:
        return Decision(True, thermal)
    if mode is Mode.GUEST and in_quiet_window(
            now, config.guest_quiet_start, config.guest_quiet_end):
        return Decision(False, thermal)
    return Decision(cycle_on(now, config.cycle_seconds), thermal)
