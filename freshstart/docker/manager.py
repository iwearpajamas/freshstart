"""Disposable Docker container manager.

Freshstart talks to the Docker Engine through the ``docker`` CLI rather than
the daemon socket, so behaviour matches what a user on the same machine gets.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import uuid
from collections.abc import Sequence
from pathlib import Path

DOCKER_BINARY = "docker"

_TIMEOUT_PULL_SECONDS = 600
_TIMEOUT_INFO_SECONDS = 30
_TIMEOUT_CP_SECONDS = 300
_TIMEOUT_EXEC_MANAGER_SECONDS = 60


class DockerError(Exception):
    """Raised when Docker is unavailable, misconfigured or a command fails."""


class DockerManager:
    """Manages one disposable container for a single Freshstart run."""

    def __init__(self, docker_binary: str = DOCKER_BINARY):
        self.docker_binary = docker_binary
        self.container_id: str | None = None
        self.container_name: str = f"freshstart-{uuid.uuid4().hex[:12]}"

    # -- low-level --------------------------------------------------------
    def _run(
        self,
        args: Sequence[str],
        timeout: float = _TIMEOUT_INFO_SECONDS,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        cmd = [self.docker_binary, *args]
        try:
            result = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=timeout
            )
        except FileNotFoundError as exc:
            raise DockerError(
                f"Docker command '{self.docker_binary}' was not found. "
                "Install Docker: https://docs.docker.com/get-docker/"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerError(f"Docker command {' '.join(cmd[:2])} timed out.") from exc
        if check and result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise DockerError(
                f"Docker command '{' '.join(cmd)}' failed with exit code {result.returncode}"
                + (f": {detail}" if detail else "")
            )
        return result

    # -- availability -------------------------------------------------------
    def docker_available(self) -> bool:
        try:
            return self._run(["--version"], check=False).returncode == 0
        except DockerError:
            return False

    def daemon_running(self) -> bool:
        try:
            return self._run(["info"], check=False).returncode == 0
        except DockerError:
            return False

    def server_version(self) -> str | None:
        try:
            result = self._run(["version", "--format", "{{.Server.Version}}"], check=False)
        except DockerError:
            return None
        if result.returncode == 0:
            return (result.stdout or "").strip() or None
        return None

    def image_exists(self, image: str) -> bool:
        try:
            return self._run(["image", "inspect", image], check=False).returncode == 0
        except DockerError:
            return False

    def pull_image(self, image: str) -> None:
        """Pull *image* unless it is already present locally."""
        if self.image_exists(image):
            return
        self._run(["pull", image], timeout=_TIMEOUT_PULL_SECONDS)

    # -- container lifecycle ------------------------------------------------
    def create_container(
        self,
        image: str,
        workdir: str = "/workspace",
        memory_mb: int = 512,
        cpus: float = 1.0,
        network: str = "none",
    ) -> str:
        """Create and start a disposable container, returning its ID."""
        cmd = [
            "run",
            "-d",
            "--name",
            self.container_name,
            "--label",
            f"freshstart.io/name={self.container_name}",
            "--label",
            "freshstart.io/tool=freshstart",
            "--cpus",
            str(cpus),
            "--memory",
            f"{memory_mb}m",
            "--pids-limit",
            "256",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--network",
            network,
            "--entrypoint",
            "/bin/sh",
            image,
            "-c",
            "sleep infinity",
        ]
        result = self._run(cmd, timeout=180)
        self.container_id = (result.stdout or "").strip().splitlines()[0] if result.stdout else ""
        if not self.container_id:
            raise DockerError("Docker returned no container ID.")
        return self.container_id

    def ensure_directory(self, path: str) -> None:
        if not self.container_id:
            raise DockerError("Container ID is not set; cannot create directory.")
        self._run(
            ["exec", self.container_id, "mkdir", "-p", path], timeout=_TIMEOUT_EXEC_MANAGER_SECONDS
        )

    def copy_project(self, staging_dir: Path, workdir: str) -> None:
        """Copy *staging_dir* into the container's *workdir* via ``docker cp``."""
        if not self.container_id:
            raise DockerError("Container ID is not set; cannot copy project.")
        staging = str(Path(staging_dir))
        # Primary form: copy the contents of the staging directory into workdir.
        source = f"{staging}{os.sep}."
        destination = f"{self.container_id}:{workdir}/"
        result = self._run(["cp", source, destination], timeout=_TIMEOUT_CP_SECONDS, check=False)
        if result.returncode == 0 and self._verify_copy(workdir):
            return
        # Fallback form for hosts/Docker versions that treat ``/.`` differently.
        result = self._run(["cp", staging, destination], timeout=_TIMEOUT_CP_SECONDS, check=False)
        if result.returncode == 0 and self._verify_copy(workdir):
            return
        detail = ((result.stderr or result.stdout or "").strip()) or "unknown error"
        raise DockerError(f"Failed to copy project into the container: {detail}")

    def _verify_copy(self, workdir: str) -> bool:
        if not self.container_id:
            return False
        script = f"ls -A {shlex.quote(workdir)} | head -n 1"
        result = self._run(["exec", self.container_id, "sh", "-c", script], check=False)
        return result.returncode == 0 and bool((result.stdout or "").strip())

    def start_container(self) -> None:
        if not self.container_id:
            raise DockerError("Container ID is not set; cannot start container.")
        self._run(["start", self.container_id], timeout=60)

    def stop_container(self) -> None:
        if not self.container_id:
            return
        self._run(["stop", self.container_id], timeout=30, check=False)

    def remove_container(self) -> None:
        if not self.container_id:
            return
        self._run(["rm", "-f", self.container_id], timeout=30, check=False)

    def cleanup(self) -> None:
        """Stop and remove the container (never raises)."""
        try:
            if self.container_id:
                self.stop_container()
                self.remove_container()
        finally:
            self.container_id = None
