"""Best-effort redaction of secrets from logs and reports."""

from __future__ import annotations

import re

_SECRET_NAME_PATTERN = r"(?:api[_-]?key|apikey|access[_-]?key|access[_-]?token|secret[_-]?key|secret[_-]?access|secret[_-]?token|secret|token|auth[_-]?token|authorization|password|passwd|credentials|private[_-]?key|client[_-]?secret|signing[_-]?key)"

_REDACTED = "***REDACTED***"

# KEY=value / KEY: value where the key smells secret-like; the value is a
# double- or single-quoted string.
_QUOTED_SECRET = re.compile(
    r"""(?i)(""" + _SECRET_NAME_PATTERN + r""")(\s*[:=]\s*)(["'])[^"'\n]*\3""",
)

# Same shape with an unquoted value.
_UNQUOTED_SECRET = re.compile(
    r"""(?i)(""" + _SECRET_NAME_PATTERN + r""")(\s*[:=]\s*)([A-Za-z0-9][A-Za-z0-9_.\-+/:=*]*)""",
)

# Common token formats with fixed prefixes.
_KNOWN_TOKEN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "***REDACTED-GITHUB-TOKEN***"),
    (re.compile(r"\bgho_[A-Za-z0-9]{20,}\b"), "***REDACTED-GITHUB-TOKEN***"),
    (re.compile(r"\bghs_[A-Za-z0-9]{20,}\b"), "***REDACTED-GITHUB-TOKEN***"),
    (re.compile(r"github_pat_[A-Za-z0-9]{20,}\b"), "***REDACTED-GITHUB-TOKEN***"),
    (re.compile(r"\bxox[bpsar]-[A-Za-z0-9-]{10,}\b"), "***REDACTED-SLACK-TOKEN***"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "***REDACTED-AWS-KEY***"),
]

_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)


def redact_secrets(text: str) -> str:
    """Redact obvious secrets from *text*.

    This is best-effort.  It catches common ``KEY=value`` / ``KEY: value``
    forms (including names prefixed to form longer identifiers, such as
    ``MY_SECRET_TOKEN``), quoted values, and well-known token formats.
    """
    if not text:
        return ""
    result = _QUOTED_SECRET.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, text)
    result = _UNQUOTED_SECRET.sub(lambda m: m.group(1) + m.group(2) + _REDACTED, result)
    for pattern, replacement in _KNOWN_TOKEN_PATTERNS:
        result = pattern.sub(replacement, result)
    result = _PRIVATE_KEY_BLOCK.sub(
        "-----BEGIN PRIVATE KEY-----\n***REDACTED***\n-----END PRIVATE KEY-----", result
    )
    return result
