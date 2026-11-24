"""Configuration file discovery and starter template tests."""

from freshstart.config import find_config_file, generate_starter_yaml, parse_config
from tests.conftest import EXAMPLES_DIR


class TestFindConfigFile:
    def test_finds_yml(self, tmp_path):
        (tmp_path / ".freshstart.yml").write_text("version: 1\nproject:\n  name: x\n")
        assert find_config_file(tmp_path) == tmp_path / ".freshstart.yml"

    def test_finds_yaml(self, tmp_path):
        (tmp_path / ".freshstart.yaml").write_text("version: 1\n")
        assert find_config_file(tmp_path) == tmp_path / ".freshstart.yaml"

    def test_prefers_yml_over_yaml(self, tmp_path):
        (tmp_path / ".freshstart.yaml").write_text("version: 1\n")
        (tmp_path / ".freshstart.yml").write_text("version: 1\n")
        found = find_config_file(tmp_path)
        assert found is not None and found.suffix == ".yml"

    def test_returns_none_when_missing(self, tmp_path):
        assert find_config_file(tmp_path) is None


class TestStarterTemplates:
    def test_python_starter_is_valid(self, tmp_path):
        target = tmp_path / ".freshstart.yml"
        target.write_text(generate_starter_yaml("sample-project", "python"))
        config = parse_config(target)
        assert config.project.name == "sample-project"

    def test_node_starter_is_valid(self, tmp_path):
        target = tmp_path / ".freshstart.yml"
        target.write_text(generate_starter_yaml("sample-project", "node"))
        config = parse_config(target)
        assert "npm" in config.steps[0].run


def test_example_projects_are_valid():
    for name in ("python-project", "node-project"):
        config = parse_config(EXAMPLES_DIR / name / ".freshstart.yml")
        assert config.steps, f"{name} example must have steps"
