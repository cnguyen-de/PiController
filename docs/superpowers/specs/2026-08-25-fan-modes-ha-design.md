# Fan Modes with Home Assistant Control

**Date:** 2026-08-25
**Status:** Approved for planning

## Problem

`rest-server.py` is a one-shot script run from cron: it turns the fan on, sleeps
five minutes, turns it off, and skips the whole thing between 22:00 and 08:00.
The temperature logic in `checkTemp()` is dead code — nothing calls it.

Three behaviors are wanted instead of one, selectable from the Home Assistant UI:

- **guest** — no fan after 21:00
- **normal** — fan every 5 minutes
- **vacation** — fan runs continuously

A one-shot cron script cannot hold the fan on continuously, and it has nothing
listening for a mode change. It becomes a long-running service.

## Behavior

### Modes

All three modes share one duty cycle and differ only in what suppresses it.

| Mode | Behavior |
|---|---|
| `normal` | 5 minutes on, 5 minutes off, around the clock |
| `guest` | Same cycle, suppressed entirely from 21:00 to 08:00 |
| `vacation` | Fan held on continuously |

`normal` has no quiet hours. The 22:00–08:00 window in the current script applies
only to `guest`, widened to start at 21:00.

Duty cycle phase is derived from the wall clock rather than an internal timer:

```
cycle_on(now) = (int(now.timestamp()) // 300) % 2 == 0
```

This aligns bursts to 5-minute boundaries of the epoch, cannot drift, and needs
no state restored after a restart.

### Thermal rule

Above **55°C** the fan runs. Below **48°C** the thermal demand releases. Between
the two it holds its previous state — hysteresis, so the fan cannot chatter
around the threshold. These are the thresholds from the existing `checkTemp()`.

The thermal rule **overrides everything**: mode, and guest quiet hours. Guest
mode's silence is therefore best-effort — silent when the Pi is cool, but the fan
will run at 3am rather than let the Pi sit hot.

This is a deliberate trade. 55°C is normal idle-to-light-load for a Pi, not an
emergency, so the thermal rule is expected to fire routinely rather than rarely.

### Decision logic

One pure function, no I/O:

```python
def decide(mode, now, temp, thermal_latched) -> Decision:
    if temp >= THERMAL_ON_C:      thermal = True
    elif temp <= THERMAL_OFF_C:   thermal = False
    else:                         thermal = thermal_latched

    if thermal:                                   return Decision(True, thermal)
    if mode is VACATION:                          return Decision(True, thermal)
    if mode is GUEST and in_quiet_window(now):    return Decision(False, thermal)
    return Decision(cycle_on(now), thermal)
```

`Decision` carries the fan state and the new thermal latch, which the caller
feeds back on the next tick. Hysteresis state is passed in and out rather than
held in a global, which keeps the function pure and directly testable.

`in_quiet_window(now)` is `now >= 21:00 or now < 08:00`.

## Architecture

A single systemd service, `pi-fan-controller`, ticking every 10 seconds:
read temperature → `decide()` → apply to fan → publish state.

| Module | Responsibility | Depends on |
|---|---|---|
| `modes.py` | `decide()`, `cycle_on()`, `in_quiet_window()`. Pure, no I/O. | stdlib only |
| `fan.py` | Wraps the `uhubctl` call. Idempotent — no subprocess spawned when already in the requested state. | `subprocess` |
| `temperature.py` | Reads `/sys/class/thermal/thermal_zone0/temp` directly. | stdlib only |
| `mqtt_bridge.py` | Discovery, subscribe, publish, availability. Transport only — no fan logic. | `paho-mqtt` |
| `state.py` | Persists the current mode to a JSON file. | stdlib only |
| `config.py` | Thresholds, timings, topics, broker credentials, uhubctl location. | stdlib only |
| `main.py` | The tick loop. Wires the modules together. | all of the above |

The split exists so that the interesting behavior — `modes.py` — is testable
without a Pi, a broker, or waiting five minutes for a cycle to turn over.

## Home Assistant integration

MQTT Discovery. Nothing is added to Home Assistant's YAML; the entity appears by
itself once the daemon connects.

**Discovery config**, published retained on connect to
`homeassistant/select/pi_fan/mode/config`:

```json
{
  "name": "Fan Mode",
  "unique_id": "pi_fan_mode",
  "command_topic": "pi-fan/mode/set",
  "state_topic": "pi-fan/mode/state",
  "options": ["guest", "normal", "vacation"],
  "availability_topic": "pi-fan/availability",
  "device": {
    "identifiers": ["pi_fan_controller"],
    "name": "Pi Fan Controller",
    "manufacturer": "Raspberry Pi"
  }
}
```

This renders as a Guest/Normal/Vacation dropdown in the HA UI.

| Topic | Direction | Retained | Purpose |
|---|---|---|---|
| `pi-fan/mode/set` | HA → Pi | no | Mode change requests |
| `pi-fan/mode/state` | Pi → HA | yes | Current mode; retained so HA shows the right value immediately after either box restarts |
| `pi-fan/availability` | Pi → HA | yes | `online` on connect, `offline` via Last Will |

Last Will means a dead daemon shows as unavailable in the UI rather than as a
stale but plausible value.

An unrecognized payload on the command topic is logged and ignored; the daemon
republishes its actual mode so HA's UI snaps back rather than showing a mode that
is not in effect.

### Mode persistence

The mode is written to a JSON state file on every change and loaded at startup,
defaulting to `normal` when the file is absent or unreadable. The Pi therefore
boots into the correct mode even when the broker is unreachable. The retained
`mode/state` message is for Home Assistant's benefit; the file is the Pi's.

## Configuration

All in `config.py`, overridable by a config file at
`/etc/pi-fan-controller.toml`, with `deploy/config.example.toml` checked in.

| Setting | Default |
|---|---|
| `thermal_on_c` | `55.0` |
| `thermal_off_c` | `48.0` |
| `cycle_seconds` | `300` |
| `guest_quiet_start` / `guest_quiet_end` | `21:00` / `08:00` |
| `tick_seconds` | `10` |
| `uhubctl_location` / `uhubctl_port` | `1-1` / `2` |
| `mqtt_host` / `mqtt_port` | *(required)* / `1883` |
| `mqtt_username` / `mqtt_password` | *(optional)* |
| `base_topic` | `pi-fan` |
| `discovery_prefix` | `homeassistant` |

The broker address and credentials are filled in on the Pi and are not committed.

## Testing

- **`modes.py`** — table-driven tests over mode × time-of-day × temperature.
  Explicitly covered: each mode's cycle behavior; guest suppressed at 22:00 and
  active at 09:00; both hysteresis edges (rising through 55, falling through 48,
  and holding at 51 in each direction); thermal override beating guest quiet
  hours; cycle phase flipping at a 5-minute boundary.
- **`fan.py`** — a fake command runner asserts `uhubctl` is invoked with the right
  arguments, and that a redundant call in the same state spawns nothing.
- **`mqtt_bridge.py`** — payload construction and topic names asserted directly.
  The broker connection itself is not unit tested.
- **`main.py`** — one test drives several ticks with an injected clock,
  temperature source, and fake fan, confirming the loop wires up correctly.

## Deployment

- `deploy/pi-fan-controller.service` — systemd unit, `Restart=always`,
  `After=network-online.target`.
- `uhubctl` needs root, so the service runs as root.
- **The existing cron entry must be removed during cutover**, or it will fight the
  daemon over the fan.
- `requirements.txt`: `paho-mqtt`.

**Deviation from the original design, made during implementation:** the
temperature reader no longer uses `gpiozero`. `CPUTemperature` reads
`/sys/class/thermal/thermal_zone0/temp`, so reading that file directly is
equivalent, removes the project's only hardware dependency, and makes the
reader testable off-Pi with a temporary file instead of a mock.

## Repository changes

- Delete `rest-server.py`. Its scheduling logic is replaced by the tick loop, and
  it has not been a REST server since commit `645f2da`.
- Delete the committed `__pycache__/rest-server.cpython-37.pyc` and add a
  `.gitignore` covering `__pycache__/`, `*.pyc`, and `.venv/`.

## Out of scope

Deliberately excluded, each roughly ten lines if wanted later:

- CPU temperature published as an MQTT sensor for graphing in HA.
- A binary sensor showing whether the fan is currently spinning.
- Any HTTP API. The FastAPI server from commit `27e8461` is not revived; MQTT is
  the only control surface.
