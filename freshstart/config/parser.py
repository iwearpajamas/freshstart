"""Parse and validate `.freshstart.yml` / `.freshstart.yaml` configuration files."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .validator import SUPPORTED_CONFIG_VERSIONS, FreshstartConfig

CONFIG_FILENAME_CANDIDATES = (".freshstart.yml", ".freshstart.yaml")


class ConfigError(Exception):
    """Raised when a configuration file is missing or invalid."""


def find_config_file(project_dir: Path) -> Path | None:
    """Return the first existing ``.freshstart.yml`` or ``.freshstart.yaml``."""
    project_dir = Path(project_dir)
    for name in CONFIG_FILENAME_CANDIDATES:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    return None


def format_validation_errors(exc: ValidationError) -> str:
    """Format a pydantic ValidationError as readable, user-facing text."""
    lines = ["Invalid configuration:"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)


def parse_config(path: Path) -> FreshstartConfig:
    """Read and validate the configuration at *path*.

    Raises :class:`ConfigError` when the file is missing, has invalid YAML
    syntax, or fails validation.
    """
    path = Path(path).resolve()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read configuration file {path}: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML syntax in {path}: {exc}") from exc
    if data is None:
        raise ConfigError(f"Configuration file {path} is empty.")
    if not isinstance(data, dict):
        raise ConfigError(
            f"Configuration file {path} must contain a mapping at the top level, "
            f"got {type(data).__name__}."
        )
    try:
        return FreshstartConfig(**data)
    except ValidationError as exc:
        raise ConfigError(format_validation_errors(exc)) from exc


def supported_versions_message() -> str:
    return f"supported versions: {list(SUPPORTED_CONFIG_VERSIONS)}"
