"""Optional integration tests that run only when Docker is available.

These execute real containers against the local Docker daemon; when Docker is
unavailable they are skipped so the suite stays green everywhere.
"""

import pytest

from freshstart.docker import DockerExecRunner, DockerManager


def _docker_available() -> bool:
    manager = DockerManager()
    try:
        return manager.docker_available() and manager.daemon_running()
    except (OSError, RuntimeError):
        return False


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason="Docker is not available in this environment"
)


@requires_docker
def test_real_container_executes_a_command():
    manager = DockerManager()
    manager.pull_image("python:3.12-slim")
    container_id = manager.create_container("python:3.12-slim")
    try:
        runner = DockerExecRunner()
        result = runner.run(
            container_id, ["python", "-c", "print('docker works')"], "/workspace", 60, 10000
        )
        assert result.returncode == 0
        assert "docker works" in result.stdout
        assert result.timed_out is False
    finally:
        manager.cleanup()


@requires_docker
def test_real_container_records_nonzero_exit():
    manager = DockerManager()
    manager.pull_image("python:3.12-slim")
    container_id = manager.create_container("python:3.12-slim")
    try:
        runner = DockerExecRunner()
        result = runner.run(container_id, ["sh", "-c", "exit 7"], "/workspace", 60, 10000)
        assert result.returncode == 7
    finally:
        manager.cleanup()
