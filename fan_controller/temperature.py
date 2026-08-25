"""CPU temperature, read straight from the kernel's thermal zone.

This is the same file gpiozero's CPUTemperature reads, so going direct costs
nothing and drops a dependency that would otherwise be untestable off-Pi.
The controller catches read failures; this stays a thin, honest reader.
"""

import pathlib

THERMAL_ZONE = "/sys/class/thermal/thermal_zone0/temp"


def read_cpu_temperature(path=THERMAL_ZONE):
    """Degrees Celsius. The kernel reports millidegrees."""
    return int(pathlib.Path(path).read_text().strip()) / 1000.0
