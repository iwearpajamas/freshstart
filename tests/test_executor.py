"""Execution engine tests using a fake runner and fake manager."""

from datetime import UTC, datetime

from freshstart.config.validator import FreshstartConfig
from freshstart.docker.runner import CommandResult
from freshstart.execution import (
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    STATUS_TIMED_OUT,
    Executor,
)
from freshstart.execution.executor import StepResult
from tests.conftest import make_config_dict


def make_config(steps):
    """Return a validated FreshstartConfig for executor tests."""
    return FreshstartConfig.model_validate(make_config_dict(steps=steps))


class FakeRunner:
    """Returns scripted CommandResults and records calls."""

    def __init__(self, results=None):
        self._results = list(results or [])
        self.calls = []

    def run(self, container_id, command, cwd, timeout_seconds, max_output_chars):
        self.calls.append(
            {
                "container_id": container_id,
                "command": list(command),
                "cwd": cwd,
                "timeout_seconds": timeout_seconds,
                "max_output_chars": max_output_chars,
            }
        )
        if self._results:
            return self._results.pop(0)
        return CommandResult(returncode=0, stdout="", stderr="")


class FakeManager:
    def __init__(self, container_id="container-123"):
        self.container_id = container_id
        self.stop_calls = 0

    def stop_container(self):
        self.stop_calls += 1


def test_passed_step_records_all_fields():
    config = make_config([{"name": "Step A", "run": ["python", "-V"]}])
    runner = FakeRunner([CommandResult(returncode=0, stdout="3.12.0\n", stderr="")])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert len(results) == 1
    result = results[0]
    assert result.status == STATUS_PASSED
    assert result.exit_code == 0
    assert result.stdout == "3.12.0\n"
    assert result.stderr == ""
    assert result.error is None
    assert result.duration_seconds >= 0
    assert result.start_time <= result.end_time
    assert result.command == ["python", "-V"]


def test_failed_step_marks_and_stops_by_default():
    config = make_config(
        [
            {"name": "Step A", "run": ["false"]},
            {"name": "Step B", "run": ["true"]},
        ]
    )
    runner = FakeRunner([CommandResult(returncode=1, stdout="", stderr="boom")])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert results[0].status == STATUS_FAILED
    assert results[0].exit_code == 1
    assert results[0].error is not None
    assert results[1].status == STATUS_SKIPPED


def test_continue_on_failure_runs_next_step():
    config = make_config(
        [
            {"name": "Step A", "run": ["false"], "continue_on_failure": True},
            {"name": "Step B", "run": ["true"]},
        ]
    )
    runner = FakeRunner([CommandResult(returncode=1), CommandResult(returncode=0)])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert results[0].status == STATUS_FAILED
    assert results[1].status == STATUS_PASSED


def test_timed_out_step_stops_container_and_skips_rest():
    config = make_config(
        [
            {"name": "Slow", "run": ["sleep"], "timeout_seconds": 5},
            {"name": "Later", "run": ["true"]},
        ]
    )
    manager = FakeManager()
    runner = FakeRunner([CommandResult(returncode=None, timed_out=True)])
    results = Executor(manager, config, runner=runner).execute()
    assert results[0].status == STATUS_TIMED_OUT
    assert results[0].error is not None
    assert manager.stop_calls == 1
    assert results[1].status == STATUS_SKIPPED


def test_error_result_marks_error():
    config = make_config([{"name": "A", "run": ["x"]}])
    runner = FakeRunner([CommandResult(returncode=None, error="boom")])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert results[0].status == STATUS_ERROR
    assert results[0].error == "boom"


def test_output_is_redacted_and_limited_by_config():
    config = make_config([{"name": "A", "run": ["x"]}])
    config.execution.max_output_chars = 100
    runner = FakeRunner([CommandResult(returncode=0, stdout="api_key=supersecret123\n")])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert "supersecret123" not in results[0].stdout
    assert "api_key=" in results[0].stdout


def test_on_step_callback_invoked_per_step():
    config = make_config([{"name": "A", "run": ["x"]}])
    runner = FakeRunner([CommandResult(returncode=0)])
    seen = []
    Executor(FakeManager(), config, runner=runner, on_step=seen.append).execute()
    assert len(seen) == 1
    assert isinstance(seen[0], StepResult)


def test_all_steps_pass_when_all_pass():
    config = make_config(
        [
            {"name": "A", "run": ["a"]},
            {"name": "B", "run": ["b"]},
        ]
    )
    runner = FakeRunner([CommandResult(returncode=0), CommandResult(returncode=0)])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert [r.status for r in results] == [STATUS_PASSED, STATUS_PASSED]


def test_skipped_results_have_no_exit_code():
    config = make_config([{"name": "A", "run": ["a"]}])
    runner = FakeRunner([CommandResult(returncode=1)])
    results = Executor(FakeManager(), config, runner=runner).execute()
    assert results[0].exit_code == 1


def test_step_result_to_dict_round_trip():
    now = datetime.now(UTC)
    result = StepResult(
        step_name="A",
        command=["a"],
        status=STATUS_PASSED,
        start_time=now,
        end_time=now,
        exit_code=0,
        stdout="out",
        stderr="",
        error=None,
    )
    data = result.to_dict()
    assert data["step_name"] == "A"
    assert data["status"] == STATUS_PASSED
    assert data["duration_seconds"] >= 0
