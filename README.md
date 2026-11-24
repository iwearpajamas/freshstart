# Freshstart — Fresh Clone Setup Tester

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Freshstart** is a developer tool that checks whether a software project can
be installed and set up successfully in a completely clean environment.

Many projects only work on the original developer's machine: extra system
packages, a different Python or Node version, undocumented setup steps,
missing files, or leftover environment state make it painful to try out a new
contribution or verify a README. Freshstart runs your project's setup steps in
a disposable Docker container and tells you what works.

## Features

- Reads a `.freshstart.yml` configuration describing your project's environment
  and setup steps.
- Pulls the image, copies the project into a disposable Docker container, and
  runs every step sequentially in the same container.
- Captures output, exit codes, and timings for every step.
- Generates detailed `freshstart-report.md` and `freshstart-report.json` reports.
- Applies safety defaults: network disabled by default, no host mounts,
  capability and resource limits, secret redaction, output truncation, and
  full cleanup of containers and temporary files.
- Works on Linux, macOS, and Windows (WSL 2 backend with Docker Desktop).

## Installation

```bash
pip install freshstart
```

Requires Python 3.11+ and a Docker Engine installation. On Windows, use WSL 2
and the Docker Desktop WSL 2 backend.

## Quick start

```bash
# 1. Add a .freshstart.yml to your project
freshstart init ./my-project

# 2. Edit the generated file to describe your setup steps

# 3. Test the project in a clean container
freshstart test ./my-project
```

`freshstart init` creates a starter `.freshstart.yml` for your project. For
example projects, see [examples/](examples/).

## Example `.freshstart.yml`

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

All commands are argument arrays (never shell strings) so commands are
executed directly without a shell.

## Example terminal output

```text
Analyzing project: my-python-project
Docker image: python:3.12-slim
[1/3] Install dependencies .. PASSED
[2/3] Run tests ................ FAILED
[3/3] Check application ........ SKIPPED

----------------------------------------
SETUP TEST FAILED

Total steps:  3
Passed:       1
Failed:       1
Skipped:      1

Main problem:
  Step 'Run tests' failed with exit code 1.

Reports:
  ./my-python-project/freshstart-report.md
  ./my-python-project/freshstart-report.json
```

## Example report

`freshstart-report.md` contains:

- Project name, directory, generation date, Docker image, environment, and
  total duration.
- Overall results (total, passed, failed, skipped, timed out).
- Per-step details: command, status, duration, exit code, and output.
- Likely explanations for failures.
- Environment information (Docker version, platform).

`freshstart-report.json` contains the same information in machine-readable
form, including step-by-step results and findings.

See [docs/configuration.md](docs/configuration.md) for the full schema.

## CLI reference

```bash
freshstart test ./my-project                  # run the setup test
freshstart test ./my-project --allow-network  # allow network access in the container
freshstart test ./my-project --config custom.yml
freshstart test ./my-project --report-dir ./reports
freshstart init ./my-project                  # create a starter .freshstart.yml
freshstart validate ./my-project              # validate configuration without Docker
freshstart --version
freshstart --help
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | All required setup steps passed. |
| `1` | One or more setup steps failed. |
| `2` | Invalid configuration or arguments. |
| `3` | Docker or infrastructure error. |
| `4` | Execution timeout. |

## GitHub Actions integration

```yaml
name: Freshstart Setup Test

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test-setup:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Run Freshstart
        uses: YOUR-ORG/freshstart@v1
        with:
          allow_network: 'true'
```

See [docs/github-actions.md](docs/github-actions.md) and
[action/action.yml](action/action.yml) for details.

## Security and limitations

- Containers are not an absolute security boundary for hostile code. Freshstart
  is intended to be used with projects you trust.
- Private keys, `.env` files, and similar files are excluded from the project
  copy by default, but that is best-effort hygiene — do not rely on it.
- Output is truncated and redacted with best-effort secret patterns; leaks can
  still occur with exotic formats.
- Docker requires root-equivalent access on Linux hosts; on Windows, WSL 2 is
  required.
- On failure, the tool reports the actual step output; not every error can be
  diagnosed automatically, and findings are suggestions supported by evidence.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy freshstart
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and
[SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## Building the standalone executable

Freshstart can be built as a single executable with
[PyInstaller](https://pyinstaller.readthedocs.io):

```bash
pip install pyinstaller
python -m PyInstaller --clean --onefile --name freshstart freshstart_exe_entry.py
```

The executable is written to `dist/freshstart.exe` (Windows) or
`dist/freshstart` (Linux/macOS).

Verify it works:

```bash
dist/freshstart.exe --version    # prints: freshstart 0.1.0
dist/freshstart.exe validate ./my-project
```

## License

MIT — see [LICENSE](LICENSE).
