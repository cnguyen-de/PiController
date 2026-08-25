"""Mode persistence, so the Pi boots into the right mode without the broker."""

import json
import logging
import pathlib

from .modes import Mode

log = logging.getLogger(__name__)

DEFAULT_MODE = Mode.NORMAL


def load_mode(path):
    """The last saved mode, or NORMAL if it cannot be read."""
    try:
        raw = json.loads(pathlib.Path(path).read_text())
        return Mode(raw["mode"])
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("no usable saved mode at %s, defaulting to %s",
                    path, DEFAULT_MODE.value)
        return DEFAULT_MODE


def save_mode(path, mode):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"mode": mode.value}))
