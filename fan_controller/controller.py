"""The tick loop's brain: read temperature, decide, apply, report."""

import logging

from .modes import Mode, decide

log = logging.getLogger(__name__)


class Controller:
    """Holds the mutable state that `decide` deliberately does not.

    Everything it touches is injected, so the whole loop runs in tests without
    a Pi, a broker, or waiting five minutes for a cycle to turn over.
    """

    def __init__(self, config, fan, read_temp, clock, mode=Mode.NORMAL,
                 on_mode_change=None):
        self._config = config
        self._fan = fan
        self._read_temp = read_temp
        self._clock = clock
        self._mode = mode
        self._thermal_latched = False
        # Public so the composition root can close the loop with the MQTT
        # bridge, which cannot exist until the controller does.
        self.on_mode_change = on_mode_change

    @property
    def mode(self):
        return self._mode

    def set_mode(self, mode):
        log.info("mode %s -> %s", self._mode.value, mode.value)
        self._mode = mode
        if self.on_mode_change:
            self.on_mode_change(mode)

    def tick(self):
        decision = decide(self._mode, self._clock(), self._temperature(),
                          self._thermal_latched, self._config)
        self._thermal_latched = decision.thermal_latched
        self._fan.set(decision.fan_on)

    def _temperature(self):
        """A sensor that cannot be read raises no thermal demand.

        Returning the release threshold keeps the mode in charge rather than
        pinning the fan on or dropping a latch that heat still justifies.
        """
        try:
            return self._read_temp()
        except Exception:
            log.exception("could not read CPU temperature")
            return self._config.thermal_off_c
