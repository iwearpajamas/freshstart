# Freshstart Configuration Reference

Freshstart reads `.freshstart.yml` (or `.freshstart.yaml`) from the project
directory. All fields except `project` and `steps` are optional.

## Top level

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `version` | `int` | `1` | Configuration format version. Supported: `1`. |
| `project.name` | `str` | required | Name used in reports and the CLI output. |
| `environment.image` | `str` | `python:3.12-slim` | Docker image to use as the clean environment. |
| `environment.workdir` | `str` | `/workspace` | Working directory inside the container (absolute path). |
| `environment.allow_network` | `bool` | `false` | Allow network access in the container. |
| `environment.memory_mb` | `int` | `512` | Container memory limit (64–16384). |
| `environment.cpus` | `float` | `1.0` | Container CPU limit (0.1–16). |
| `execution.overall_timeout_seconds` | `int` | `3600` | Wall-clock limit for the whole run. |
| `execution.max_output_chars` | `int` | `30000` | Maximum stdout/stderr characters kept per step. |
| `steps` | `StepConfig[]` | required (at least 1) | Setup steps executed sequentially. |

## Steps

Every step runs in the same container, so installed packages and generated
files remain available to later steps.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `str` | required | Human-readable step name (1–200 chars). |
| `run` | `str[]` | required | Argument array, executed via `docker exec`. |
| `timeout_seconds` | `int` | `300` | Per-step timeout (1–86400). |
| `continue_on_failure` | `bool` | `false` | Continue to later steps after this step fails. |
| `env` | `dict` | unset | Extra environment variables for the step. |

Validation is strict on purpose:

- Commands must be non-empty strings in an argument array. Shell strings are
  not allowed; if you deliberately need a shell, pass it explicitly
  (for example `run: ["sh", "-lc", "pip install -e ."]`).
- Unknown keys are rejected so typos are never silently ignored.
- `version` must be `1`.

## Full example

```yaml
version: 1

project:
  name: example-project

environment:
  image: python:3.12-slim
  workdir: /workspace
  allow_network: false

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

  - name: Run tests
    run:
      - python
      - -m
      - pytest
      - -q
    timeout_seconds: 120
```

Use `freshstart validate ./project` to check a configuration without running
Docker.
