"""Shared helpers for the Freshstart test suite."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


def make_config_dict(**overrides):
    """A minimal valid configuration as a plain dict (pydantic validates it)."""
    base = {
        "version": 1,
        "project": {"name": "test-project"},
        "steps": [{"name": "Step one", "run": ["python", "-c", "print('hi')"]}],
    }
    base.update(overrides)
    return base
