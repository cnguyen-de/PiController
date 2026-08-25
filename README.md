# Pi Fan Controller

Cycles a USB-powered fan on a Raspberry Pi, with three modes switchable from the
Home Assistant UI.

## Modes

| Mode | Behavior |
|---|---|
| `normal` | 5 minutes on, 5 minutes off, around the clock |
| `guest` | Same cycle, silent from 21:00 to 08:00 |
| `vacation` | Fan runs continuously |

Above **55°C** the fan runs regardless of mode or hour, releasing at **48°C**.
Guest mode's silence is therefore best-effort: quiet while the Pi is cool, but
the fan will run at 3am rather than let it sit hot. Both thresholds, the quiet
window, and the cycle length are configurable.

## Home Assistant

The daemon publishes an MQTT Discovery config on connect, so a **Fan Mode**
dropdown appears by itself under the *Pi Fan Controller* device. Nothing needs
adding to Home Assistant's YAML — only an MQTT broker (typically the Mosquitto
add-on) that both boxes can reach.

| Topic | Direction | Retained |
|---|---|---|
| `pi-fan/mode/set` | HA → Pi | no |
| `pi-fan/mode/state` | Pi → HA | yes |
| `pi-fan/availability` | Pi → HA | yes (`offline` via Last Will) |

The mode is also written to disk, so the Pi boots into the right mode even when
the broker is unreachable.

## Install on the Pi

```sh
sudo apt install uhubctl
sudo mkdir -p /opt/pi-fan-controller
sudo cp -r fan_controller /opt/pi-fan-controller/
sudo python3 -m venv /opt/pi-fan-controller/.venv
sudo /opt/pi-fan-controller/.venv/bin/pip install -r requirements.txt

sudo cp deploy/config.example.toml /etc/pi-fan-controller.toml
sudo nano /etc/pi-fan-controller.toml     # broker address and credentials

sudo cp deploy/pi-fan-controller.service /etc/systemd/system/
sudo systemctl enable --now pi-fan-controller
```

Find your hub's location and port with `uhubctl` and set `uhubctl_location` /
`uhubctl_port` to match.

**Remove the old cron entry** (`crontab -e`) — the daemon now owns the fan, and
leaving cron in place means the two fight over it.

Check on it with `journalctl -u pi-fan-controller -f`.

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

The tests run anywhere — no Pi, no broker, and nothing waits for a real
five-minute cycle. `fan_controller/modes.py` holds the decision logic as pure
functions; everything with I/O is injected.
