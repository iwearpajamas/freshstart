"""Docker ``docker exec`` runner with output limits and timeouts.

Captures stdout/stderr with size limits and supports per-command timeouts so
an unbounded process cannot hang a Freshstart run forever.
"""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class CommandResult:
    """The outcome of one ``docker exec`` invocation."""

    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None


class OutputCollector:
    """Collect subprocess output while enforcing a maximum character count."""

    def __init__(self, limit: int):
        self.limit = limit
        self._parts: list[str] = []
        self._kept = 0
        self.received = 0
        self.truncated = False

    def append(self, text: str) -> None:
        if not text:
            return
        self.received += len(text)
        remaining = self.limit - self._kept
        if remaining <= 0:
            self.truncated = True
            return
        if len(text) > remaining:
            self._parts.append(text[:remaining])
            self._kept += remaining
            self.truncated = True
        else:
            self._parts.append(text)
            self._kept += len(text)

    @property
    def text(self) -> str:
        body = "".join(self._parts)
        if self.truncated:
            omitted = max(0, self.received - self._kept)
            return f"{body}\n[output truncated: {omitted} additional bytes omitted]"
        return body


class DockerExecRunner:
    """Runs commands via ``docker exec`` inside a running container."""

    def __init__(self, docker_binary: str = "docker", chunk_size: int = 8192):
        self.docker_binary = docker_binary
        self.chunk_size = chunk_size

    def run(
        self,
        container_id: str,
        command: Sequence[str],
        cwd: str,
        timeout_seconds: int,
        max_output_chars: int,
    ) -> CommandResult:
        cmd = [
            self.docker_binary,
            "exec",
            "-w",
            cwd,
            container_id,
            *[str(item) for item in command],
        ]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            return CommandResult(
                returncode=None, error=f"Failed to start '{self.docker_binary} exec': {exc}"
            )

        stdout_collector = OutputCollector(max_output_chars)
        stderr_collector = OutputCollector(max_output_chars)

        def _pump(stream, collector) -> None:
            try:
                while True:
                    chunk = stream.read(self.chunk_size)
                    if not chunk:
                        break
                    collector.append(chunk)
            except (OSError, ValueError):
                pass
            finally:
                stream.close()

        threads = [
            threading.Thread(target=_pump, args=(proc.stdout, stdout_collector), daemon=True),
            threading.Thread(target=_pump, args=(proc.stderr, stderr_collector), daemon=True),
        ]
        for thread in threads:
            thread.start()

        timed_out = False
        error: str | None = None
        try:
            proc.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            error = f"Command timed out after {timeout_seconds} seconds."
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        except OSError as exc:
            error = f"Failed to wait on command process: {exc}"

        for thread in threads:
            thread.join(timeout=5)

        if error is None and proc.returncode is None:
            error = "Process did not report an exit code."

        return CommandResult(
            returncode=proc.returncode,
            stdout=stdout_collector.text,
            stderr=stderr_collector.text,
            timed_out=timed_out,
            error=error,
        )
