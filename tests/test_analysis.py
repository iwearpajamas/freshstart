"""Result-analysis tests."""

from datetime import UTC, datetime

from freshstart.execution import STATUS_FAILED, STATUS_TIMED_OUT
from freshstart.execution.analysis import analyze_results
from freshstart.execution.executor import StepResult


def failed_result(stdout="", stderr=""):
    now = datetime.now(UTC)
    return StepResult(
        step_name="Failing step",
        command=["python", "-m", "pip", "install", "-r", "requirements.txt"],
        status=STATUS_FAILED,
        start_time=now,
        end_time=now,
        exit_code=1,
        stdout=stdout,
        stderr=stderr,
    )


def timed_out_result():
    now = datetime.now(UTC)
    return StepResult(
        step_name="Slow step",
        command=["python", "-m", "pytest"],
        status=STATUS_TIMED_OUT,
        start_time=now,
        end_time=now,
        exit_code=None,
        stdout="",
        stderr="",
        error="Command timed out after 300 seconds.",
    )


def kinds(findings):
    return [finding.kind for finding in findings]


def test_timeout_finding():
    findings = analyze_results([timed_out_result()])
    assert kinds(findings) == ["step-timeout"]
    assert findings[0].message.startswith("Step 'Slow step' timed out")
    assert findings[0].suggestion


def test_missing_python_module_finding():
    result = failed_result(stderr="ModuleNotFoundError: No module named 'flask'")
    findings = analyze_results([result])
    assert "missing-python-module" in kinds(findings)
    module_finding = next(f for f in findings if f.kind == "missing-python-module")
    assert "flask" in module_finding.message


def test_missing_package_pip_finding():
    result = failed_result(
        stderr="ERROR: Could not find a version that satisfies the requirement pydantic-foo"
    )
    findings = analyze_results([result])
    assert "missing-package" in kinds(findings)


def test_missing_node_module_finding():
    result = failed_result(stderr="Cannot find module 'express'")
    findings = analyze_results([result])
    assert "missing-node-module" in kinds(findings)


def test_missing_file_finding():
    result = failed_result(stderr="No such file or directory: 'requirements.txt'")
    findings = analyze_results([result])
    assert "missing-file" in kinds(findings)


def test_network_error_finding():
    result = failed_result(stderr="Temporary failure in name resolution")
    findings = analyze_results([result])
    assert "network-error" in kinds(findings)


def test_no_findings_for_passed_steps():
    now = datetime.now(UTC)
    result = StepResult(
        step_name="Ok",
        command=["echo", "hi"],
        status="PASSED",
        start_time=now,
        end_time=now,
        exit_code=0,
        stdout="hi",
        stderr="",
    )
    assert analyze_results([result]) == []


def test_findings_include_evidence():
    result = failed_result(stdout="some evidence text")
    findings = analyze_results([result])
    assert findings
    assert findings[0].kind == "step-failed"
    assert findings[0].evidence == "some evidence text"
