from fan_controller.modes import Mode
from fan_controller.state import load_mode, save_mode


def test_a_saved_mode_is_read_back(tmp_path):
    path = tmp_path / "state.json"

    save_mode(path, Mode.VACATION)

    assert load_mode(path) is Mode.VACATION


def test_saving_twice_keeps_the_most_recent_mode(tmp_path):
    path = tmp_path / "state.json"

    save_mode(path, Mode.VACATION)
    save_mode(path, Mode.GUEST)

    assert load_mode(path) is Mode.GUEST


def test_a_missing_file_falls_back_to_normal(tmp_path):
    assert load_mode(tmp_path / "absent.json") is Mode.NORMAL


def test_unreadable_json_falls_back_to_normal(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")

    assert load_mode(path) is Mode.NORMAL


def test_an_unrecognised_mode_name_falls_back_to_normal(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"mode": "party"}')

    assert load_mode(path) is Mode.NORMAL


def test_saving_creates_missing_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "state.json"

    save_mode(path, Mode.GUEST)

    assert load_mode(path) is Mode.GUEST
