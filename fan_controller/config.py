"""Every tunable in one place, overridable by a TOML file on the Pi."""

import dataclasses
import datetime
import logging
import pathlib
import tomllib

log = logging.getLogger(__name__)

DEFAULT_PATH = "/etc/pi-fan-controller.toml"
_TIME_FIELDS = ("guest_quiet_start", "guest_quiet_end")


@dataclasses.dataclass(frozen=True)
class Config:
    # Thermal override. Above `on`, the fan runs regardless of mode or hour;
    # below `off` the demand releases. The gap between them is the hysteresis
    # that stops the fan chattering around the threshold.
    thermal_on_c: float = 55.0
    thermal_off_c: float = 48.0

    cycle_seconds: int = 300
    tick_seconds: int = 10

    guest_quiet_start: datetime.time = datetime.time(21, 0)
    guest_quiet_end: datetime.time = datetime.time(8, 0)

    uhubctl_location: str = "1-1"
    uhubctl_port: str = "2"

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None

    base_topic: str = "pi-fan"
    discovery_prefix: str = "homeassistant"

    state_file: str = "/var/lib/pi-fan-controller/state.json"


def load_config(path=DEFAULT_PATH):
    """Config defaults with any values from `path` layered on top."""
    try:
        raw = tomllib.loads(pathlib.Path(path).read_text())
    except OSError:
        log.info("no config file at %s, using defaults", path)
        return Config()
    except tomllib.TOMLDecodeError:
        log.exception("malformed config at %s, using defaults", path)
        return Config()

    known = {f.name for f in dataclasses.fields(Config)}
    for key in set(raw) - known:
        log.warning("ignoring unknown config key %r", key)

    values = {key: raw[key] for key in raw.keys() & known}
    for field in _TIME_FIELDS:
        if field in values:
            values[field] = datetime.time.fromisoformat(values[field])

    return Config(**values)
