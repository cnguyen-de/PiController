from fan_controller.fan import Fan


class RecordingRunner:
    """Stands in for subprocess, recording the argv it was handed."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)


def test_turning_the_fan_on_powers_the_configured_hub_port():
    runner = RecordingRunner()

    Fan(runner, location="1-1", port="2").set(True)

    assert runner.calls == [["uhubctl", "-l", "1-1", "-p", "2", "-a", "1"]]


def test_turning_the_fan_off_cuts_power_to_the_same_port():
    runner = RecordingRunner()

    Fan(runner, location="1-1", port="2").set(False)

    assert runner.calls == [["uhubctl", "-l", "1-1", "-p", "2", "-a", "0"]]


def test_the_first_call_always_issues_a_command_because_hardware_state_is_unknown():
    runner = RecordingRunner()

    Fan(runner).set(False)

    assert len(runner.calls) == 1


def test_repeating_the_current_state_issues_no_command():
    runner = RecordingRunner()
    fan = Fan(runner)

    fan.set(True)
    fan.set(True)
    fan.set(True)

    assert len(runner.calls) == 1


def test_changing_state_issues_a_command_each_time():
    runner = RecordingRunner()
    fan = Fan(runner)

    fan.set(True)
    fan.set(False)
    fan.set(True)

    assert len(runner.calls) == 3


def test_is_on_reports_the_last_requested_state():
    fan = Fan(RecordingRunner())
    assert fan.is_on is None

    fan.set(True)
    assert fan.is_on is True

    fan.set(False)
    assert fan.is_on is False


def test_a_failed_command_is_not_recorded_as_the_new_state():
    def failing_runner(argv):
        raise OSError("uhubctl not found")

    fan = Fan(failing_runner)

    fan.set(True)

    assert fan.is_on is None
