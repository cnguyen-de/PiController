"""Entry point: wire the pieces together and tick forever."""

import argparse
import datetime
import logging
import signal
import sys
import time

from .config import DEFAULT_PATH, load_config
from .controller import Controller
from .fan import Fan
from .mqtt_bridge import MqttBridge
from .state import load_mode, save_mode
from .temperature import read_cpu_temperature

log = logging.getLogger("fan_controller")


def build(config, client):
    """Assemble the controller and bridge over an already-created MQTT client.

    The two refer to each other — a mode arriving from Home Assistant drives
    the controller, and a mode set anywhere gets published back — so the
    callbacks are attached after both exist.
    """
    controller = Controller(
        config=config,
        fan=Fan(location=config.uhubctl_location, port=config.uhubctl_port),
        read_temp=read_cpu_temperature,
        clock=datetime.datetime.now,
        mode=load_mode(config.state_file),
    )
    bridge = MqttBridge(client, config, on_mode_change=controller.set_mode)

    def persist_and_publish(mode):
        save_mode(config.state_file, mode)
        bridge.publish_mode(mode)

    controller.on_mode_change = persist_and_publish
    bridge.prepare()
    return controller, bridge


def run(config, client, controller, bridge, should_continue=lambda: True):
    """Tick until told to stop. Broker trouble must not stop the fan."""
    client.on_connect = lambda c, userdata, flags, rc, *a: bridge.handle_connect(
        controller.mode)
    client.on_message = lambda c, userdata, msg: bridge.handle_message(
        msg.topic, msg.payload)

    try:
        client.connect_async(config.mqtt_host, config.mqtt_port)
        client.loop_start()
    except Exception:
        log.exception("could not start MQTT; continuing without Home Assistant")

    while should_continue():
        controller.tick()
        time.sleep(config.tick_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Raspberry Pi fan controller")
    parser.add_argument("--config", default=DEFAULT_PATH)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config(args.config)

    import paho.mqtt.client as mqtt
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    controller, bridge = build(config, client)

    running = True

    def stop(signum, frame):
        nonlocal running
        log.info("received signal %s, shutting down", signum)
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("starting in %s mode", controller.mode.value)
    run(config, client, controller, bridge, should_continue=lambda: running)
    return 0


if __name__ == "__main__":
    sys.exit(main())
