"""Result analysis: turn raw step output into likely explanations.

Findings are best-effort.  A finding is reported only when there is concrete
evidence in the command output (a captured error message, missing module,
and so on); the accompanying suggestion is guidance, not a diagnosis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .executor import STATUS_FAILED, STATUS_TIMED_OUT, StepResult


@dataclass
class Finding:
    """A likely explanation for a failed step, with a suggested next step."""

    kind: str
    message: str
    evidence: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "message": self.message,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
        }


def _evidence(text: str, limit: int = 200) -> str | None:
    trimmed = text.strip()
    return trimmed[:limit] if trimmed else None


def analyze_results(results: list[StepResult]) -> list[Finding]:
    """Return findings for failed or timed-out steps, best-effort."""
    findings: list[Finding] = []
    for result in results:
        if result.status == STATUS_TIMED_OUT:
            findings.append(
                Finding(
                    kind="step-timeout",
                    message=(
                        f"Step '{result.step_name}' timed out after "
                        f"{result.duration_seconds:.1f} seconds."
                    ),
                    evidence=_evidence(result.error or ""),
                    suggestion=(
                        "Increase the step's timeout_seconds in .freshstart.yml, or optimise "
                        "the step (for example caching downloads or running checks in parallel)."
                    ),
                )
            )
            continue
        if result.status != STATUS_FAILED:
            continue
        findings.append(
            Finding(
                kind="step-failed",
                message=f"Step '{result.step_name}' failed with exit code {result.exit_code}.",
                evidence=_evidence(result.stderr or result.stdout or ""),
            )
        )
        findings.extend(_analyze_failure_output(result))
    return findings


def _analyze_failure_output(result: StepResult) -> list[Finding]:
    """Extract likely explanations from failed step output (best-effort)."""
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    findings: list[Finding] = []
    seen_kinds = set()

    # Each spec: (kind, pattern, message_template, suggestion).
    specs = [
        (
            "missing-python-module",
            re.compile(r"[Mm]oduleNotFoundError:\s*[Nn]o module named\s+['\"]?([A-Za-z0-9_.-]+)"),
            "Missing Python module: {subject}",
            (
                "Install the module in the project, for example add it to requirements.txt or "
                "pyproject.toml, or run `python -m pip install {subject}`."
            ),
        ),
        (
            "missing-python-module",
            re.compile(r"[Ii]mportError:\s*[Nn]o module named\s+['\"]?([A-Za-z0-9_.-]+)"),
            "Missing Python module: {subject}",
            (
                "Install the module in the project (e.g. add it to requirements.txt or run "
                "`python -m pip install {subject}`)."
            ),
        ),
        (
            "missing-package",
            re.compile(r"No matching distribution found for\s+([A-Za-z0-9_.\-]+)"),
            "Missing package: {subject}",
            (
                "The package could not be found by pip. Check the name and version pin, and that "
                "the package index is reachable (try `freshstart test . --allow-network`)."
            ),
        ),
        (
            "missing-package",
            re.compile(
                r"ERROR: Could not find a version that satisfies the requirement\s+([A-Za-z0-9_.\-]+)"
            ),
            "Missing package: {subject}",
            (
                "No distribution of the package was found. Check the name/version pin and network "
                "access, then install it with `python -m pip install {subject}`."
            ),
        ),
        (
            "missing-package",
            re.compile(r"npm ERR!\s+[^\n]*404[^\n]*", re.IGNORECASE),
            "Missing Node.js package (npm 404)",
            (
                "The package was not found in the npm registry. Check the name in package.json or "
                "the registry it is published to."
            ),
        ),
        (
            "missing-node-module",
            re.compile(r"Cannot find module\s+['\"]?([^'\"\n]+)"),
            "Cannot find Node.js module: {subject}",
            (
                "A required Node.js module is missing. Run `npm install` so the package is linked "
                "into node_modules."
            ),
        ),
        (
            "missing-file",
            re.compile(r"(?:No such file or directory|ENOENT)[^\n]{0,160}"),
            "A file reported as missing: {subject}",
            (
                "Check that the file exists in the repository and is not gitignored, or update the "
                "setup steps to create it."
            ),
        ),
        (
            "docker-error",
            re.compile(
                r"(?:Unable to find image|docker: Error response from daemon|No such image)",
                re.IGNORECASE,
            ),
            "Docker image problem detected",
            (
                "Check the image name in .freshstart.yml and run `docker pull <image>` manually to "
                "see the full error."
            ),
        ),
        (
            "network-error",
            re.compile(
                r"(?:Temporary failure in name resolution|Name or service not known|"
                r"network is unreachable|Could not resolve host|Connection refused)",
                re.IGNORECASE,
            ),
            "Network error detected",
            (
                "Network access is disabled by default in Freshstart. Run `freshstart test . "
                "--allow-network` or set `allow_network: true` in the configuration."
            ),
        ),
    ]

    for kind, pattern, message_template, suggestion in specs:
        if kind in seen_kinds:
            continue
        match = pattern.search(text)
        if match is None:
            continue
        seen_kinds.add(kind)
        subject = match.group(1).strip() if match.groups() else ""
        message = message_template.format(subject=subject) if subject else message_template
        findings.append(
            Finding(
                kind=kind,
                message=message,
                evidence=_evidence(match.group(0)),
                suggestion=suggestion.format(subject=subject) if subject else suggestion,
            )
        )
    return findings


__all__ = ["Finding", "analyze_results"]
