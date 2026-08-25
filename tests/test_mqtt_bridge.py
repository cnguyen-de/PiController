import json

from fan_controller.config import Config
from fan_controller.modes import Mode
from fan_controller.mqtt_bridge import MqttBridge, discovery_payload, topics


class FakeClient:
    """Stands in for paho's client, recording what the bridge asks of it."""

    def __init__(self):
        self.published = []
        self.subscribed = []
        self.will = None
        self.credentials = None

    def publish(self, topic, payload, retain=False, qos=0):
        self.published.append((topic, payload, retain))

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def will_set(self, topic, payload, retain=False, qos=0):
        self.will = (topic, payload, retain)

    def username_pw_set(self, username, password):
        self.credentials = (username, password)


def payload_for(client, topic):
    return next(p for t, p, _ in client.published if t == topic)


def retain_for(client, topic):
    return next(r for t, _, r in client.published if t == topic)


class TestTopics:
    def test_topics_are_built_from_the_configured_base(self):
        t = topics(Config(base_topic="attic-fan", discovery_prefix="ha"))

        assert t.command == "attic-fan/mode/set"
        assert t.state == "attic-fan/mode/state"
        assert t.availability == "attic-fan/availability"
        assert t.discovery == "ha/select/pi_fan/mode/config"


class TestDiscoveryPayload:
    def test_it_offers_the_three_modes_home_assistant_should_show(self):
        assert discovery_payload(Config())["options"] == ["guest", "normal", "vacation"]

    def test_it_points_home_assistant_at_the_bridge_topics(self):
        payload = discovery_payload(Config())

        assert payload["command_topic"] == "pi-fan/mode/set"
        assert payload["state_topic"] == "pi-fan/mode/state"
        assert payload["availability_topic"] == "pi-fan/availability"

    def test_it_carries_a_stable_unique_id_and_device_so_entities_are_not_duplicated(self):
        payload = discovery_payload(Config())

        assert payload["unique_id"] == "pi_fan_mode"
        assert payload["device"]["identifiers"] == ["pi_fan_controller"]


class TestConnecting:
    def test_the_last_will_marks_the_entity_offline_if_the_pi_disappears(self):
        client = FakeClient()

        MqttBridge(client, Config(), lambda mode: None).prepare()

        assert client.will == ("pi-fan/availability", "offline", True)

    def test_credentials_are_only_set_when_configured(self):
        client = FakeClient()
        MqttBridge(client, Config(), lambda mode: None).prepare()
        assert client.credentials is None

        with_auth = FakeClient()
        config = Config(mqtt_username="pi", mqtt_password="secret")
        MqttBridge(with_auth, config, lambda mode: None).prepare()
        assert with_auth.credentials == ("pi", "secret")

    def test_connecting_announces_the_entity_to_home_assistant(self):
        client = FakeClient()
        bridge = MqttBridge(client, Config(), lambda mode: None)

        bridge.handle_connect(Mode.GUEST)

        announced = json.loads(payload_for(client, "homeassistant/select/pi_fan/mode/config"))
        assert announced["unique_id"] == "pi_fan_mode"
        assert retain_for(client, "homeassistant/select/pi_fan/mode/config") is True

    def test_connecting_reports_the_pi_as_online(self):
        client = FakeClient()

        MqttBridge(client, Config(), lambda mode: None).handle_connect(Mode.NORMAL)

        assert payload_for(client, "pi-fan/availability") == "online"
        assert retain_for(client, "pi-fan/availability") is True

    def test_connecting_publishes_the_current_mode_so_the_ui_matches_reality(self):
        client = FakeClient()

        MqttBridge(client, Config(), lambda mode: None).handle_connect(Mode.VACATION)

        assert payload_for(client, "pi-fan/mode/state") == "vacation"
        assert retain_for(client, "pi-fan/mode/state") is True

    def test_connecting_subscribes_to_mode_changes(self):
        client = FakeClient()

        MqttBridge(client, Config(), lambda mode: None).handle_connect(Mode.NORMAL)

        assert client.subscribed == ["pi-fan/mode/set"]


class TestIncomingModeChanges:
    def test_a_known_mode_is_handed_to_the_callback(self):
        received = []
        bridge = MqttBridge(FakeClient(), Config(), received.append)

        bridge.handle_message("pi-fan/mode/set", b"vacation")

        assert received == [Mode.VACATION]

    def test_whitespace_and_casing_are_tolerated(self):
        received = []
        bridge = MqttBridge(FakeClient(), Config(), received.append)

        bridge.handle_message("pi-fan/mode/set", b"  Guest\n")

        assert received == [Mode.GUEST]

    def test_an_unknown_mode_is_ignored(self):
        received = []
        bridge = MqttBridge(FakeClient(), Config(), received.append)

        bridge.handle_message("pi-fan/mode/set", b"party")

        assert received == []

    def test_an_unknown_mode_republishes_the_real_mode_so_the_ui_snaps_back(self):
        client = FakeClient()
        bridge = MqttBridge(client, Config(), lambda mode: None)
        bridge.handle_connect(Mode.GUEST)
        client.published.clear()

        bridge.handle_message("pi-fan/mode/set", b"party")

        assert client.published == [("pi-fan/mode/state", "guest", True)]


class TestPublishingMode:
    def test_the_mode_is_published_retained(self):
        client = FakeClient()
        bridge = MqttBridge(client, Config(), lambda mode: None)

        bridge.publish_mode(Mode.VACATION)

        assert client.published == [("pi-fan/mode/state", "vacation", True)]
