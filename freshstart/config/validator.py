"""Pydantic models describing the Freshstart configuration.

Validation rules:

* The configuration ``version`` must be one of :data:`SUPPORTED_CONFIG_VERSIONS`.
* Every step has a non-empty ``name`` and a non-empty ``run`` list whose
  items are strings (argument arrays, not shell strings).
* Timeouts are positive and bounded; ``timeout_seconds`` default 300.
* The ``image`` is a non-empty single-line string.
* Unknown keys are rejected (``extra="forbid"``) so typos are never ignored.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_CONFIG_VERSIONS = (1,)

MAX_NAME_LENGTH = 200
MAX_TIMEOUT_SECONDS = 86400
DEFAULT_STEP_TIMEOUT_SECONDS = 300


class StepConfig(BaseModel):
    """One setup step executed inside the container."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    run: list[str] = Field(min_length=1)
    timeout_seconds: int = Field(default=DEFAULT_STEP_TIMEOUT_SECONDS, gt=0, le=MAX_TIMEOUT_SECONDS)
    continue_on_failure: bool = False
    env: dict[str, str] | None = None

    @field_validator("run")
    @classmethod
    def _validate_commands(cls, value: list[Any]) -> list[str]:
        commands: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(  # noqa: TRY004 - pydantic wraps ValueError as ValidationError
                    "commands must be strings (argument arrays, not shell strings)"
                )
            if not item.strip():
                raise ValueError("commands must not be empty strings")
            commands.append(item)
        return commands

    @field_validator("env")
    @classmethod
    def _validate_env(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("env keys must be non-empty strings")
            if not isinstance(item, str):
                raise ValueError("env values must be strings")  # noqa: TRY004 - see above
        return value


class EnvironmentConfig(BaseModel):
    """The Docker container environment the steps run in."""

    model_config = ConfigDict(extra="forbid")

    image: str = Field(default="python:3.12-slim", min_length=1, max_length=255)
    workdir: str = Field(default="/workspace", min_length=1)
    allow_network: bool = False
    memory_mb: int = Field(default=512, ge=64, le=16384)
    cpus: float = Field(default=1.0, gt=0.0, le=16.0)

    @field_validator("image")
    @classmethod
    def _validate_image(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("image must not be empty")
        if "\n" in value or "\r" in value:
            raise ValueError("image must be a single line")
        return value

    @field_validator("workdir")
    @classmethod
    def _validate_workdir(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/"):
            raise ValueError("workdir must be an absolute path (e.g. /workspace)")
        if len(value) > 200:
            raise ValueError("workdir must be at most 200 characters")
        return value


class ExecutionConfig(BaseModel):
    """Runtime limits for the execution engine and container resources."""

    model_config = ConfigDict(extra="forbid")

    overall_timeout_seconds: int = Field(default=3600, gt=0, le=30 * MAX_TIMEOUT_SECONDS)
    max_output_chars: int = Field(default=30000, gt=0, le=10_000_000)
    memory_mb: int = Field(default=512, ge=64, le=16384)
    cpus: float = Field(default=1.0, gt=0.0, le=16.0)


class ProjectConfig(BaseModel):
    """Project metadata used in reports."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)


class FreshstartConfig(BaseModel):
    """The full Freshstart configuration (``.freshstart.yml``)."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    project: ProjectConfig
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    steps: list[StepConfig]

    @field_validator("version")
    @classmethod
    def _validate_version(cls, value: int) -> int:
        if value not in SUPPORTED_CONFIG_VERSIONS:
            raise ValueError(
                f"unsupported configuration version {value}; "
                f"supported versions: {list(SUPPORTED_CONFIG_VERSIONS)}"
            )
        return value

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[StepConfig]) -> list[StepConfig]:
        if not value:
            raise ValueError("steps must contain at least one step")
        return value
