from fan_controller.config import Config, load_config


def test_a_missing_file_yields_the_documented_defaults(tmp_path):
    config = load_config(tmp_path / "absent.toml")

    assert config == Config()
    assert config.thermal_on_c == 55.0
    assert config.thermal_off_c == 48.0
    assert config.cycle_seconds == 300
    assert config.tick_seconds == 10
    assert config.mqtt_port == 1883
    assert config.base_topic == "pi-fan"
    assert config.discovery_prefix == "homeassistant"


def test_file_values_override_the_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('mqtt_host = "homeassistant.local"\nthermal_on_c = 62.5\n')

    config = load_config(path)

    assert config.mqtt_host == "homeassistant.local"
    assert config.thermal_on_c == 62.5


def test_unspecified_values_keep_their_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('mqtt_host = "broker"\n')

    config = load_config(path)

    assert config.thermal_off_c == 48.0
    assert config.uhubctl_port == "2"


def test_unknown_keys_are_ignored_rather_than_crashing_the_daemon(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('mqtt_host = "broker"\nfavourite_colour = "blue"\n')

    config = load_config(path)

    assert config.mqtt_host == "broker"
    assert not hasattr(config, "favourite_colour")


def test_quiet_hours_are_parsed_from_clock_strings(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('guest_quiet_start = "22:30"\nguest_quiet_end = "07:00"\n')

    config = load_config(path)

    assert (config.guest_quiet_start.hour, config.guest_quiet_start.minute) == (22, 30)
    assert (config.guest_quiet_end.hour, config.guest_quiet_end.minute) == (7, 0)
