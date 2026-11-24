"""Shared result summaries used by the CLI, Markdown and JSON reports."""

from __future__ import annotations

from typing import Any

from ..execution.executor import StepResult


def build_summary(results: list[StepResult]) -> dict[str, Any]:
    """Count step statuses and derive the overall status.

    Overall status is ``PASSED`` when nothing failed; otherwise ``FAILED``.
    """
    counts = {
        "passed": 0,
        "failed": 0,
        "timed_out": 0,
        "skipped": 0,
        "errors": 0,
    }
    total_duration = 0.0
    for result in results:
        key = result.status.lower()
        if key in counts:
            counts[key] += 1
        elif key == "error":
            counts["errors"] += 1
        total_duration += result.duration_seconds
    failed_or_error = counts["failed"] + counts["timed_out"] + counts["errors"]
    return {
        "total_steps": len(results),
        **counts,
        "overall_status": "FAILED" if failed_or_error else "PASSED",
        "duration_seconds": round(total_duration, 3),
    }


__all__ = ["build_summary"]
