"""Fan hardware control via uhubctl, which cuts power to a USB hub port."""

import logging
import subprocess

log = logging.getLogger(__name__)


def run_command(argv):
    subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


class Fan:
    """Switches the fan, skipping the subprocess when already in the wanted state.

    `is_on` starts as None because the hardware's state at startup is unknown,
    so the first request always issues a command to establish a known state.
    """

    def __init__(self, runner=run_command, location="1-1", port="2"):
        self._runner = runner
        self._location = location
        self._port = port
        self.is_on = None

    def set(self, on):
        if self.is_on is on:
            return

        argv = ["uhubctl", "-l", self._location, "-p", self._port,
                "-a", "1" if on else "0"]
        try:
            self._runner(argv)
        except (OSError, subprocess.SubprocessError):
            # Leave is_on unchanged so the next tick retries rather than
            # assuming a state the hardware never reached.
            log.exception("failed to switch fan %s", "on" if on else "off")
            return

        log.info("fan %s", "on" if on else "off")
        self.is_on = on
