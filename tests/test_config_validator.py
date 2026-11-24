"""Configuration validation and parsing tests."""

import pytest
from pydantic import ValidationError

from freshstart.config import ConfigError, parse_config
from freshstart.config.validator import FreshstartConfig
from tests.conftest import make_config_dict


class TestValidConfig:
    def test_minimal_config_parses(self):
        config = FreshstartConfig.model_validate(make_config_dict())
        assert config.version == 1
        assert config.project.name == "test-project"
        assert config.steps[0].name == "Step one"
        assert config.environment.image == "python:3.12-slim"
        assert config.environment.workdir == "/workspace"
        assert config.environment.allow_network is False
        assert config.execution.overall_timeout_seconds == 3600
        assert config.execution.max_output_chars == 30000

    def test_full_config_parses(self):
        config = FreshstartConfig.model_validate(
            make_config_dict(
                version=1,
                project={"name": "full"},
                environment={"image": "node:22-slim", "workdir": "/app", "allow_network": True},
                execution={"overall_timeout_seconds": 60, "max_output_chars": 1000},
                steps=[
                    {
                        "name": "Run",
                        "run": ["npm", "install"],
                        "timeout_seconds": 5,
                        "continue_on_failure": True,
                    }
                ],
            )
        )
        assert config.environment.image == "node:22-slim"
        assert config.environment.allow_network is True
        assert config.steps[0].timeout_seconds == 5
        assert config.steps[0].continue_on_failure is True


class TestInvalidConfig:
    @pytest.mark.parametrize("version", [0, 2, -1, "9"])
    def test_unsupported_version(self, version):
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(make_config_dict(version=version))

    def test_missing_project(self):
        data = make_config_dict()
        del data["project"]
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_step_missing_name(self):
        data = make_config_dict(steps=[{"run": ["echo", "hi"]}])
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_step_empty_name(self):
        data = make_config_dict(steps=[{"name": "", "run": ["echo"]}])
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    @pytest.mark.parametrize(
        "run",
        [[], [""], ["   "], ["ok", ""], ["ok", 123], "echo hello"],
    )
    def test_invalid_run(self, run):
        data = make_config_dict(steps=[{"name": "Step", "run": run}])
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    @pytest.mark.parametrize("timeout", [0, -5, 86401])
    def test_invalid_timeout_seconds(self, timeout):
        data = make_config_dict(
            steps=[{"name": "Step", "run": ["echo"], "timeout_seconds": timeout}]
        )
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_invalid_image_empty(self):
        data = make_config_dict(environment={"image": ""})
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_invalid_workdir_relative(self):
        data = make_config_dict(environment={"workdir": "workspace"})
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_unknown_key_rejected(self):
        data = make_config_dict(surprise_key=True)
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)

    def test_no_steps(self):
        data = make_config_dict(steps=[])
        with pytest.raises(ValidationError):
            FreshstartConfig.model_validate(data)


class TestParseConfigFile:
    def test_parse_valid_file(self, tmp_path):
        path = tmp_path / ".freshstart.yml"
        path.write_text(
            "version: 1\nproject:\n  name: parsed-project\nsteps:\n  - name: S\n    run: [python]\n"
        )
        config = parse_config(path)
        assert config.project.name == "parsed-project"

    def test_missing_file_raises_config_error(self, tmp_path):
        with pytest.raises(ConfigError):
            parse_config(tmp_path / "nope.yml")

    def test_invalid_yaml_raises_config_error(self, tmp_path):
        path = tmp_path / ".freshstart.yml"
        path.write_text("version: [unclosed\n  :::")
        with pytest.raises(ConfigError):
            parse_config(path)

    def test_empty_file_raises_config_error(self, tmp_path):
        path = tmp_path / ".freshstart.yml"
        path.write_text("")
        with pytest.raises(ConfigError):
            parse_config(path)

    def test_non_mapping_top_level_raises_config_error(self, tmp_path):
        path = tmp_path / ".freshstart.yml"
        path.write_text("- just\n- a list\n")
        with pytest.raises(ConfigError):
            parse_config(path)
