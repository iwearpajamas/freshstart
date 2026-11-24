"""Generate the human-readable Markdown report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ..config.validator import FreshstartConfig
from ..execution.analysis import Finding
from ..execution.executor import StepResult
from .summary import build_summary


def _format_duration(seconds: float) -> str:
    return f"{seconds:.2f}s"


def _format_command(command: list[str]) -> str:
    return " ".join(command)


def _append_output(lines: list[str], label: str, text: str) -> None:
    lines.append(f"- **{label}:**")
    lines.append("")
    if text:
        lines.append("```text")
        lines.append(text.rstrip())
        lines.append("```")
    else:
        lines.append("*(no output)*")
    lines.append("")


def generate_markdown_report(
    config: FreshstartConfig,
    results: list[StepResult],
    findings: list[Finding],
    project_dir: Path,
    environment: dict[str, str],
    total_duration_seconds: float,
    generated_at: datetime | None = None,
) -> str:
    """Render the Markdown report as a string."""
    generated_at = generated_at or datetime.now(UTC)
    summary = build_summary(results)

    lines: list[str] = ["# Freshstart Setup Test Report", ""]

    lines.append("## Project Information")
    lines.append("")
    lines.append(f"- **Project name:** {config.project.name}")
    lines.append(f"- **Project directory:** {Path(project_dir).resolve()}")
    lines.append(f"- **Generated:** {generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"- **Docker image:** {config.environment.image}")
    lines.append(
        f"- **Docker network:** {'enabled' if config.environment.allow_network else 'disabled'}"
    )
    env_text = ", ".join(f"{key}: {value}" for key, value in environment.items()) or "(none)"
    lines.append(f"- **Environment:** {env_text}")
    lines.append(f"- **Total duration:** {total_duration_seconds:.2f}s")
    lines.append("")

    lines.append("## Overall Results")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("| --- | --- |")
    lines.append(f"| Total steps | {summary['total_steps']} |")
    lines.append(f"| Passed | {summary['passed']} |")
    lines.append(f"| Failed | {summary['failed']} |")
    lines.append(f"| Skipped | {summary['skipped']} |")
    lines.append(f"| Timed out | {summary['timed_out']} |")
    lines.append(f"| Errors | {summary['errors']} |")
    lines.append(f"| **Overall status** | **{summary['overall_status']}** |")
    lines.append("")

    lines.append("## Step Details")
    lines.append("")
    for index, result in enumerate(results, start=1):
        lines.append(f"### {index}. {result.step_name}")
        lines.append("")
        lines.append(f"- **Command:** `{_format_command(result.command)}`")
        lines.append(f"- **Status:** {result.status}")
        lines.append(f"- **Duration:** {result.duration_seconds:.2f}s")
        exit_code = result.exit_code if result.exit_code is not None else "n/a"
        lines.append(f"- **Exit code:** {exit_code}")
        lines.append(f"- **Started:** {result.start_time.strftime('%H:%M:%S UTC')}")
        lines.append(f"- **Ended:** {result.end_time.strftime('%H:%M:%S UTC')}")
        lines.append("")
        _append_output(lines, "Output", result.stdout)
        if result.stderr:
            _append_output(lines, "Error output", result.stderr)
        if result.error:
            lines.append(f"- **Error:** {result.error}")
            lines.append("")
    lines.append("")

    lines.append("## Failure Explanations")
    lines.append("")
    if not findings:
        lines.append("No failure explanations available.")
        lines.append("")
    for finding in findings:
        lines.append(f"- **{finding.kind}:** {finding.message}")
        if finding.evidence:
            lines.append(f"  - Evidence: `{finding.evidence}`")
        if finding.suggestion:
            lines.append(f"  - Suggestion: {finding.suggestion}")
    lines.append("")

    lines.append("## Environment Information")
    lines.append("")
    for key, value in environment.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    return "\n".join(lines)


def write_markdown_report(path: Path, content: str) -> Path:
    """Write *content* to *path*, creating parent directories."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


__all__ = ["generate_markdown_report", "write_markdown_report"]
