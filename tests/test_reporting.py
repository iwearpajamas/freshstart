"""Reporting tests: Markdown, JSON, summary."""

from datetime import UTC, datetime
from pathlib import Path

from freshstart.config.validator import FreshstartConfig
from freshstart.execution import (
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_SKIPPED,
    STATUS_TIMED_OUT,
)
from freshstart.execution.analysis import Finding
from freshstart.execution.executor import StepResult
from freshstart.reporting import (
    build_json_report,
    build_summary,
    generate_markdown_report,
    write_json_report,
    write_markdown_report,
)
from tests.conftest import make_config_dict


def make_result(name="Step A", status=STATUS_PASSED, exit_code=0, stdout="ok output", stderr=""):
    now = datetime.now(UTC)
    return StepResult(
        step_name=name,
        command=["python", "-c", "print('x')"],
        status=status,
        start_time=now,
        end_time=now,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        error=None if status == STATUS_PASSED else "Command exited with code 1.",
    )


def make_config():
    return FreshstartConfig.model_validate(make_config_dict(project={"name": "md-project"}))


def test_markdown_report_contains_project_info():
    config = make_config()
    report = generate_markdown_report(
        config,
        [make_result()],
        [],
        Path("/proj"),
        {"docker_version": "24.0.7", "platform": "linux"},
        1.25,
    )
    assert "# Freshstart Setup Test Report" in report
    assert "md-project" in report
    assert "python:3.12-slim" in report
    assert "docker_version: 24.0.7" in report


def test_markdown_report_contains_step_details():
    config = make_config()
    report = generate_markdown_report(
        config,
        [make_result(name="Install", stdout="hello")],
        [],
        Path("/proj"),
        {"docker_version": "24"},
        1.25,
    )
    assert "## Step Details" in report
    assert "Install" in report
    assert "PASSED" in report
    assert "hello" in report
    assert "python -c print('x')" in report


def test_markdown_report_includes_failure_section():
    config = make_config()
    findings = [
        Finding(kind="step-failed", message="Step 'B' failed with exit code 1.", evidence="boom")
    ]
    report = generate_markdown_report(
        config,
        [make_result(name="B", status=STATUS_FAILED, exit_code=1)],
        findings,
        Path("/proj"),
        {"docker_version": "24"},
        0.5,
    )
    assert "## Failure Explanations" in report
    assert "Step 'B' failed with exit code 1." in report


def test_markdown_write_creates_file(tmp_path):
    config = make_config()
    content = generate_markdown_report(config, [make_result()], [], tmp_path, {}, 1.0)
    target = tmp_path / "reports" / "freshstart-report.md"
    result_path = write_markdown_report(target, content)
    assert result_path == target
    assert target.read_text(encoding="utf-8") == content


def test_json_report_structure():
    config = make_config()
    results = [
        make_result(name="A", status=STATUS_PASSED),
        make_result(name="B", status=STATUS_FAILED, exit_code=1),
    ]
    findings = [Finding(kind="step-failed", message="B failed", evidence="x")]
    data = build_json_report(
        config,
        results,
        findings,
        Path("/proj"),
        {"docker_version": "24"},
        2.5,
    )
    assert data["project"]["name"] == "md-project"
    assert data["environment"]["image"] == "python:3.12-slim"
    assert data["summary"]["total_steps"] == 2
    assert data["summary"]["passed"] == 1
    assert data["summary"]["failed"] == 1
    assert data["summary"]["overall_status"] == "FAILED"
    assert [step["step_name"] for step in data["steps"]] == ["A", "B"]
    assert data["findings"][0]["kind"] == "step-failed"
    assert data["freshstart_version"]


def test_json_write_creates_file(tmp_path):
    config = make_config()
    data = build_json_report(config, [make_result()], [], tmp_path, {}, 1.0)
    target = tmp_path / "reports" / "freshstart-report.json"
    result_path = write_json_report(target, data)
    assert result_path == target
    assert target.exists()
    assert target.read_text(encoding="utf-8").strip().startswith("{")


def test_summary_counts_statuses():
    now = datetime.now(UTC)
    results = [
        StepResult("A", ["a"], STATUS_PASSED, now, now, 0, "", ""),
        StepResult("B", ["b"], STATUS_FAILED, now, now, 1, "", ""),
        StepResult("C", ["c"], STATUS_TIMED_OUT, now, now, None, "", ""),
        StepResult("D", ["d"], STATUS_SKIPPED, now, now, None, "", ""),
        StepResult("E", ["e"], STATUS_ERROR, now, now, None, "", "boom"),
    ]
    summary = build_summary(results)
    assert summary["total_steps"] == 5
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["timed_out"] == 1
    assert summary["skipped"] == 1
    assert summary["errors"] == 1
    assert summary["overall_status"] == "FAILED"


def test_summary_passed_when_all_pass_or_skipped():
    now = datetime.now(UTC)
    results = [
        StepResult("A", ["a"], STATUS_PASSED, now, now, 0, "", ""),
        StepResult("B", ["b"], STATUS_SKIPPED, now, now, None, "", ""),
    ]
    assert build_summary(results)["overall_status"] == "PASSED"


def test_summary_passed_when_all_pass():
    now = datetime.now(UTC)
    results = [StepResult("A", ["a"], STATUS_PASSED, now, now, 0, "", "")]
    assert build_summary(results)["overall_status"] == "PASSED"
