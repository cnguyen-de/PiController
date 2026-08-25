"""Home Assistant integration over MQTT Discovery.

The entity appears in the HA UI on its own; nothing is added to HA's YAML.
This module owns transport only — it holds no fan logic.
"""

import json
import logging
from typing import NamedTuple

from .modes import Mode

log = logging.getLogger(__name__)

ONLINE = "online"
OFFLINE = "offline"


class Topics(NamedTuple):
    command: str
    state: str
    availability: str
    discovery: str


def topics(config):
    return Topics(
        command=f"{config.base_topic}/mode/set",
        state=f"{config.base_topic}/mode/state",
        availability=f"{config.base_topic}/availability",
        discovery=f"{config.discovery_prefix}/select/pi_fan/mode/config",
    )


def discovery_payload(config):
    """The HA Discovery config that renders the mode dropdown."""
    t = topics(config)
    return {
        "name": "Fan Mode",
        "unique_id": "pi_fan_mode",
        "command_topic": t.command,
        "state_topic": t.state,
        "availability_topic": t.availability,
        "options": [mode.value for mode in Mode],
        "device": {
            "identifiers": ["pi_fan_controller"],
            "name": "Pi Fan Controller",
            "manufacturer": "Raspberry Pi",
        },
    }


class MqttBridge:
    """Translates between the broker and the controller's mode."""

    def __init__(self, client, config, on_mode_change):
        self._client = client
        self._config = config
        self._on_mode_change = on_mode_change
        self._topics = topics(config)
        self._mode = None

    def prepare(self):
        """Configure the client before it connects."""
        if self._config.mqtt_username:
            self._client.username_pw_set(self._config.mqtt_username,
                                         self._config.mqtt_password)
        # Registered before connecting so the broker publishes it if we die.
        self._client.will_set(self._topics.availability, OFFLINE, retain=True)

    def handle_connect(self, mode):
        """Announce the entity and its current state, then listen for changes."""
        self._client.publish(self._topics.discovery,
                             json.dumps(discovery_payload(self._config)),
                             retain=True)
        self._client.publish(self._topics.availability, ONLINE, retain=True)
        self.publish_mode(mode)
        self._client.subscribe(self._topics.command)

    def handle_message(self, topic, payload):
        if topic != self._topics.command:
            return

        raw = payload.decode("utf-8", errors="replace").strip().lower()
        try:
            mode = Mode(raw)
        except ValueError:
            log.warning("ignoring unknown mode %r", raw)
            # Snap the UI back to what is actually in effect.
            if self._mode is not None:
                self.publish_mode(self._mode)
            return

        self._on_mode_change(mode)

    def publish_mode(self, mode):
        """Retained, so HA shows the right value as soon as it reconnects."""
        self._mode = mode
        self._client.publish(self._topics.state, mode.value, retain=True)
