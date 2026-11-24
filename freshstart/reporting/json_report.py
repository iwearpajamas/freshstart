"""Generate the machine-readable JSON report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import __version__
from ..config.validator import FreshstartConfig
from ..execution.analysis import Finding
from ..execution.executor import StepResult
from .summary import build_summary


def build_json_report(
    config: FreshstartConfig,
    results: list[StepResult],
    findings: list[Finding],
    project_dir: Path,
    environment: dict[str, str],
    total_duration_seconds: float,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the JSON report as a dictionary."""
    generated_at = generated_at or datetime.now(UTC)
    return {
        "freshstart_version": __version__,
        "generated_at": generated_at.isoformat(),
        "project": {
            "name": config.project.name,
            "directory": str(Path(project_dir).resolve()),
        },
        "environment": {
            "image": config.environment.image,
            "workdir": config.environment.workdir,
            "allow_network": config.environment.allow_network,
            "memory_mb": config.execution.memory_mb,
            "cpus": config.execution.cpus,
            **environment,
        },
        "summary": build_summary(results),
        "steps": [result.to_dict() for result in results],
        "findings": [finding.to_dict() for finding in findings],
    }


def write_json_report(path: Path, data: dict[str, Any]) -> Path:
    """Write the JSON report to *path*, creating parent directories."""
    import json

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


__all__ = ["build_json_report", "write_json_report"]
