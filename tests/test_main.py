from fan_controller.config import Config
from fan_controller.main import build
from fan_controller.modes import Mode
from fan_controller.state import load_mode, save_mode


class FakeClient:
    def __init__(self):
        self.published = []
        self.subscribed = []
        self.will = None

    def publish(self, topic, payload, retain=False, qos=0):
        self.published.append((topic, payload, retain))

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def will_set(self, topic, payload, retain=False, qos=0):
        self.will = (topic, payload, retain)

    def username_pw_set(self, username, password):
        pass


def test_the_controller_starts_in_the_mode_that_was_saved(tmp_path):
    state = tmp_path / "state.json"
    save_mode(state, Mode.VACATION)

    controller, _ = build(Config(state_file=str(state)), FakeClient())

    assert controller.mode is Mode.VACATION


def test_the_controller_starts_in_normal_when_nothing_was_saved(tmp_path):
    controller, _ = build(Config(state_file=str(tmp_path / "absent.json")),
                          FakeClient())

    assert controller.mode is Mode.NORMAL


def test_a_mode_change_is_written_to_disk_so_it_survives_a_reboot(tmp_path):
    state = tmp_path / "state.json"
    controller, _ = build(Config(state_file=str(state)), FakeClient())

    controller.set_mode(Mode.GUEST)

    assert load_mode(state) is Mode.GUEST


def test_a_mode_change_is_published_so_home_assistant_follows(tmp_path):
    client = FakeClient()
    controller, _ = build(Config(state_file=str(tmp_path / "s.json")), client)

    controller.set_mode(Mode.GUEST)

    assert ("pi-fan/mode/state", "guest", True) in client.published


def test_a_mode_arriving_from_home_assistant_drives_the_controller(tmp_path):
    state = tmp_path / "state.json"
    controller, bridge = build(Config(state_file=str(state)), FakeClient())

    bridge.handle_message("pi-fan/mode/set", b"vacation")

    assert controller.mode is Mode.VACATION
    assert load_mode(state) is Mode.VACATION
