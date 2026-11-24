"""Execution engine: sequential step execution and result analysis."""

from .analysis import Finding, analyze_results
from .executor import (
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    STATUS_TIMED_OUT,
    Executor,
    StepResult,
)

__all__ = [
    "STATUS_ERROR",
    "STATUS_FAILED",
    "STATUS_PASSED",
    "STATUS_SKIPPED",
    "STATUS_TIMED_OUT",
    "Executor",
    "Finding",
    "StepResult",
    "analyze_results",
]
