"""CLI tests using typer.testing.CliRunner."""

from pathlib import Path

from typer.testing import CliRunner

from freshstart import __version__
from freshstart.cli import app
from tests.conftest import EXAMPLES_DIR

runner = CliRunner()


class TestVersionAndHelp:
    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_help_lists_commands(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("test", "init", "validate"):
            assert command in result.output


class TestTestCommand:
    def test_missing_directory_is_exit_2(self):
        result = runner.invoke(app, ["test", str(Path(r"C:\missing-dir-xyz"))])
        assert result.exit_code == 2
        assert "not found" in result.output

    def test_directory_without_config_is_exit_2(self, tmp_path):
        result = runner.invoke(app, ["test", str(tmp_path)])
        assert result.exit_code == 2
        assert "No configuration file found" in result.output

    def test_test_runs_when_docker_unavailable_is_exit_3(self, tmp_path, monkeypatch):
        (tmp_path / ".freshstart.yml").write_text(
            "version: 1\nproject:\n  name: t\nsteps:\n  - name: A\n    run: [python]\n"
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.docker_available", lambda self: False
        )
        result = runner.invoke(app, ["test", str(tmp_path)])
        assert result.exit_code == 3
        assert "Docker was not found" in result.output

    def test_test_reports_are_generated_end_to_end(self, tmp_path, monkeypatch):
        # End-to-end with Docker "available" and mocked container commands.
        project = EXAMPLES_DIR / "python-project"
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.docker_available", lambda self: True
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.daemon_running", lambda self: True
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.pull_image", lambda self, image: None
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.create_container",
            lambda self, **kwargs: "abc123",
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.copy_project",
            lambda self, staging, workdir: None,
        )
        monkeypatch.setattr(
            "freshstart.docker.manager.DockerManager.start_container", lambda self: None
        )
        monkeypatch.setattr("freshstart.docker.manager.DockerManager.cleanup", lambda self: None)

        from freshstart.docker.runner import CommandResult
        from freshstart.execution import Executor

        class FakeRunner:
            def run(self, container_id, command, cwd, timeout_seconds, max_output_chars):
                return CommandResult(returncode=0, stdout="ok\n")

        monkeypatch.setattr(
            "freshstart.cli.Executor",
            lambda manager, config, **kw: Executor(manager, config, runner=FakeRunner()),
        )

        report_dir = tmp_path / "reports"
        result = runner.invoke(app, ["test", str(project), "--report-dir", str(report_dir)])
        assert result.exit_code == 0, result.output
        assert (report_dir / "freshstart-report.md").exists()
        assert (report_dir / "freshstart-report.json").exists()
        assert "SETUP TEST PASSED" in result.output


class TestInitCommand:
    def test_init_creates_config(self, tmp_path):
        target = tmp_path / "proj"
        result = runner.invoke(app, ["init", str(target)])
        assert result.exit_code == 0
        config = target / ".freshstart.yml"
        assert config.exists()
        assert "version: 1" in config.read_text(encoding="utf-8")


class TestValidateCommand:
    def test_validate_python_example(self):
        result = runner.invoke(app, ["validate", str(EXAMPLES_DIR / "python-project")])
        assert result.exit_code == 0
        assert "is valid" in result.output

    def test_validate_node_example(self):
        result = runner.invoke(app, ["validate", str(EXAMPLES_DIR / "node-project")])
        assert result.exit_code == 0

    def test_validate_invalid_config_is_exit_2(self, tmp_path):
        (tmp_path / ".freshstart.yml").write_text("version: 2\n")
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 2

    def test_validate_missing_dir_is_exit_2(self):
        result = runner.invoke(app, ["validate", str(Path(r"C:\missing-dir-xyz"))])
        assert result.exit_code == 2
