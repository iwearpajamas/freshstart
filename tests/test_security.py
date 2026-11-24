"""Secret redaction tests."""

from freshstart.utils.security import redact_secrets


def test_redacts_api_key_without_space():
    assert redact_secrets("api_key=abc123") == "api_key=***REDACTED***"


def test_redacts_quoted_password():
    result = redact_secrets('password="hunter2"')
    assert "hunter2" not in result
    assert result == "password=***REDACTED***"


def test_redacts_token_with_colon_separator():
    result = redact_secrets("token: supersecret")
    assert "supersecret" not in result
    assert result == "token: ***REDACTED***"


def test_redacts_env_style_assignment_with_prefix():
    result = redact_secrets("export MY_SECRET_TOKEN=abcdef123456")
    assert "abcdef123456" not in result
    assert "MY_SECRET_TOKEN=***REDACTED***" in result


def test_redacts_github_token():
    token = "ghp_" + "A" * 40
    result = redact_secrets(f"auth: {token}")
    assert "ghp_" not in result
    assert "***REDACTED-GITHUB-TOKEN***" in result


def test_redacts_private_key_block():
    text = "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADAN\n-----END PRIVATE KEY-----"
    result = redact_secrets(text)
    assert "MIIEvQIBADAN" not in result
    assert "PRIVATE KEY" in result


def test_leaves_normal_text_unchanged():
    text = "All checks passed, 2 files written, no errors."
    assert redact_secrets(text) == text


def test_empty_string_is_safe():
    assert redact_secrets("") == ""
