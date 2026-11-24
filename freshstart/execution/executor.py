"""Sequential execution engine for the configured setup steps.

Each step runs through ``docker exec`` in the same long-lived container so
installed packages and generated files persist between steps.  Every step is
recorded with its command, timings, exit code, output, and status.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from ..config.validator import FreshstartConfig, StepConfig
from ..docker.manager import DockerError
from ..docker.runner import CommandResult, DockerExecRunner
from ..utils.security import redact_secrets

STATUS_PASSED = "PASSED"
STATUS_FAILED = "FAILED"
STATUS_TIMED_OUT = "TIMED_OUT"
STATUS_SKIPPED = "SKIPPED"
STATUS_ERROR = "ERROR"


@dataclass
class StepResult:
    """The outcome of executing one configured step."""

    step_name: str
    command: list[str]
    status: str
    start_time: datetime
    end_time: datetime
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "command": list(self.command),
            "status": self.status,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": round(self.duration_seconds, 3),
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
        }


class Executor:
    """Runs the configured steps sequentially against the container."""

    def __init__(
        self,
        docker_manager,
        config: FreshstartConfig,
        runner: DockerExecRunner | None = None,
        on_step: Callable[[StepResult], None] | None = None,
    ):
        self.manager = docker_manager
        self.config = config
        self.runner = runner or DockerExecRunner()
        self.on_step = on_step
        self.results: list[StepResult] = []

    def execute(self) -> list[StepResult]:
        """Run all steps and return their results.

        Stops on failure unless the step sets ``continue_on_failure``.  On
        timeout the container is stopped and remaining steps are SKIPPED.
        """
        start_monotonic = time.monotonic()
        for step in self.config.steps:
            if time.monotonic() - start_monotonic > self.config.execution.overall_timeout_seconds:
                self.results.append(self._skipped_result(step))
                break
            result = self._run_step(step)
            self.results.append(result)
            if self.on_step is not None:
                self.on_step(result)
            if result.status == STATUS_TIMED_OUT:
                # Stop the execution environment safely; the remaining steps
                # are recorded as skipped below.
                try:
                    self.manager.stop_container()
                except DockerError:
                    pass
                break
            if result.status == STATUS_ERROR:
                break
            if result.status == STATUS_FAILED and not step.continue_on_failure:
                break
        # Steps after a break are recorded as skipped so nothing silently
        # disappears from the report.
        executed = len(self.results)
        for step in self.config.steps[executed:]:
            self.results.append(self._skipped_result(step))
        return self.results

    def _run_step(self, step: StepConfig) -> StepResult:
        start_time = datetime.now(UTC)
        mono_start = time.monotonic()
        command = list(step.run)
        result: CommandResult = self.runner.run(
            container_id=self.manager.container_id or "",
            command=command,
            cwd=self.config.environment.workdir,
            timeout_seconds=step.timeout_seconds,
            max_output_chars=self.config.execution.max_output_chars,
        )
        time.monotonic() - mono_start
        end_time = datetime.now(UTC)

        if result.timed_out:
            status = STATUS_TIMED_OUT
            error = result.error or f"Command timed out after {step.timeout_seconds} seconds."
        elif result.error is not None:
            status = STATUS_ERROR
            error = result.error
        elif result.returncode == 0:
            status = STATUS_PASSED
            error = None
        else:
            status = STATUS_FAILED
            error = f"Command exited with code {result.returncode}."

        return StepResult(
            step_name=step.name,
            command=command,
            status=status,
            start_time=start_time,
            end_time=end_time,
            exit_code=result.returncode,
            stdout=redact_secrets(result.stdout),
            stderr=redact_secrets(result.stderr),
            error=error,
        )

    def _skipped_result(self, step: StepConfig) -> StepResult:
        now = datetime.now(UTC)
        return StepResult(
            step_name=step.name,
            command=list(step.run),
            status=STATUS_SKIPPED,
            start_time=now,
            end_time=now,
            exit_code=None,
            stdout="",
            stderr="",
            error=None,
        )


__all__ = [
    "STATUS_ERROR",
    "STATUS_FAILED",
    "STATUS_PASSED",
    "STATUS_SKIPPED",
    "STATUS_TIMED_OUT",
    "Executor",
    "StepResult",
]
