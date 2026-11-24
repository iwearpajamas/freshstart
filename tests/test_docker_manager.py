"""DockerManager unit tests with mocked subprocess."""

import subprocess
from unittest import mock

import pytest

from freshstart.docker import DockerError, DockerManager


def completed(rc=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


class TestAvailability:
    def test_docker_available(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run", return_value=completed(rc=0)):
            assert manager.docker_available() is True

    def test_docker_not_installed(self):
        manager = DockerManager()
        with mock.patch(
            "freshstart.docker.manager.subprocess.run", side_effect=FileNotFoundError("docker")
        ):
            assert manager.docker_available() is False

    def test_daemon_running(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run", return_value=completed(rc=0)):
            assert manager.daemon_running() is True

    def test_daemon_down(self):
        manager = DockerManager()
        with mock.patch(
            "freshstart.docker.manager.subprocess.run",
            return_value=completed(rc=1, stderr="Cannot connect to the Docker daemon"),
        ):
            assert manager.daemon_running() is False

    def test_server_version_parsed(self):
        manager = DockerManager()
        with mock.patch(
            "freshstart.docker.manager.subprocess.run", return_value=completed(stdout="25.0.7\n")
        ):
            assert manager.server_version() == "25.0.7"


class TestPullImage:
    def test_pull_runs_when_image_missing(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            run.side_effect = [completed(rc=1), completed(rc=0)]
            manager.pull_image("python:3.12-slim")
        assert run.call_count == 2
        assert run.call_args_list[1].args[0][1] == "pull"

    def test_pull_skipped_when_image_exists(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            run.return_value = completed(rc=0)
            manager.pull_image("python:3.12-slim")
        assert run.call_count == 1

    def test_pull_failure_raises(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            run.side_effect = [completed(rc=1), completed(rc=1, stderr="not found")]
            with pytest.raises(DockerError):
                manager.pull_image("missing-image:latest")


class TestCreateContainer:
    def test_create_container_sets_id_and_security_flags(self):
        manager = DockerManager()
        with mock.patch(
            "freshstart.docker.manager.subprocess.run",
            return_value=completed(stdout="abc123\n"),
        ) as run:
            container_id = manager.create_container("python:3.12-slim")
        assert container_id == "abc123"
        assert manager.container_id == "abc123"
        cmd = run.call_args.args[0]
        assert cmd[1] == "run"
        assert "--cap-drop" in cmd
        assert cmd[cmd.index("--cap-drop") + 1] == "ALL"
        assert "--network" in cmd
        assert cmd[cmd.index("--network") + 1] == "none"
        assert "--security-opt" in cmd
        assert cmd[cmd.index("--security-opt") + 1] == "no-new-privileges"

    def test_create_container_failure_raises(self):
        manager = DockerManager()
        with (
            mock.patch(
                "freshstart.docker.manager.subprocess.run",
                return_value=completed(rc=1, stderr="Error response from daemon"),
            ),
            pytest.raises(DockerError),
        ):
            manager.create_container("bad-image")


class TestCopyProject:
    def test_copy_project_issues_cp_and_verifies(self, tmp_path):
        manager = DockerManager()
        manager.container_id = "c1"
        staging = tmp_path / "staging"
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            run.side_effect = [completed(rc=0), completed(rc=0, stdout="file\n")]
            manager.copy_project(staging, "/workspace")
        cmds = [call.args[0] for call in run.call_args_list]
        assert cmds[0][1] == "cp"

    def test_copy_project_failure_raises(self, tmp_path):
        manager = DockerManager()
        manager.container_id = "c1"
        staging = tmp_path / "staging"
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            run.return_value = completed(rc=1, stderr="copy failed")
            with pytest.raises(DockerError):
                manager.copy_project(staging, "/workspace")


class TestLifecycle:
    def test_start_container(self):
        manager = DockerManager()
        manager.container_id = "c1"
        with mock.patch(
            "freshstart.docker.manager.subprocess.run", return_value=completed(rc=0)
        ) as run:
            manager.start_container()
        assert run.call_args.args[0][1:3] == ["start", "c1"]

    def test_cleanup_stops_and_removes(self):
        manager = DockerManager()
        manager.container_id = "c1"
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            manager.cleanup()
        cmds = [call.args[0][1] for call in run.call_args_list]
        assert "stop" in cmds
        assert "rm" in cmds
        assert manager.container_id is None

    def test_cleanup_without_container_is_noop(self):
        manager = DockerManager()
        with mock.patch("freshstart.docker.manager.subprocess.run") as run:
            manager.cleanup()
        run.assert_not_called()
