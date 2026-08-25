import pytest

from fan_controller.temperature import read_cpu_temperature


def test_millidegrees_from_the_thermal_zone_are_converted_to_celsius(tmp_path):
    zone = tmp_path / "temp"
    zone.write_text("54321\n")

    assert read_cpu_temperature(zone) == pytest.approx(54.321)


def test_a_missing_thermal_zone_raises(tmp_path):
    with pytest.raises(OSError):
        read_cpu_temperature(tmp_path / "absent")


def test_unparseable_contents_raise(tmp_path):
    zone = tmp_path / "temp"
    zone.write_text("warm")

    with pytest.raises(ValueError):
        read_cpu_temperature(zone)
