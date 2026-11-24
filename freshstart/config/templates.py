"""Generate starter `.freshstart.yml` configurations for new projects."""

from __future__ import annotations

from pathlib import Path

STARTER_PYTHON_YAML = """\
version: 1

project:
  name: {name}

environment:
  image: python:3.12-slim
  workdir: /workspace
  allow_network: true

steps:
  - name: Install dependencies
    run:
      - python
      - -m
      - pip
      - install
      - -r
      - requirements.txt
    timeout_seconds: 300

  - name: Verify project
    run:
      - python
      - -c
      - "import main"
    timeout_seconds: 60
"""

STARTER_NODE_YAML = """\
version: 1

project:
  name: {name}

environment:
  image: node:22-slim
  workdir: /workspace
  allow_network: true

steps:
  - name: Install dependencies
    run:
      - npm
      - install
    timeout_seconds: 300

  - name: Run check
    run:
      - node
      - -v
    timeout_seconds: 60
"""


def generate_starter_yaml(project_name: str, language: str = "unknown") -> str:
    """Return a sample `.freshstart.yml` for *project_name*."""
    name = (project_name or "my-project").strip() or "my-project"
    if language == "node":
        return STARTER_NODE_YAML.format(name=name)
    return STARTER_PYTHON_YAML.format(name=name)


def write_starter_config(project_dir: Path, language: str = "unknown") -> Path:
    """Write a starter `.freshstart.yml` into *project_dir* and return its path."""
    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / ".freshstart.yml"
    target.write_text(generate_starter_yaml(project_dir.name, language), encoding="utf-8")
    return target
