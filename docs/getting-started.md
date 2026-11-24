# Freshstart — Getting Started

Freshstart (Fresh Clone Setup Tester) checks whether a software project can be
installed and set up successfully in a completely clean environment.

It reads a `.freshstart.yml` file from the project, creates a disposable
Docker container, copies the project into it, runs the configured setup steps,
and generates Markdown and JSON reports.

## Prerequisites

- Python 3.11 or later
- A Docker Engine installation (the tool uses the `docker` CLI):
  - [Docker Desktop](https://www.docker.com/products/docker-desktop/) on Windows and macOS
  - Docker Engine on Linux
- On Windows, ensure WSL 2 is enabled and Docker Desktop uses the WSL 2 backend.

## Installation

```bash
pip install freshstart
```

Or from a source checkout:

```bash
git clone https://github.com/your-org/freshstart.git
cd freshstart
pip install -e .
```

## Quick start

Generate a starter configuration for your project:

```bash
freshstart init ./my-project
```

This creates `my-project/.freshstart.yml`. Edit it to describe your setup steps.

Then test the project:

```bash
freshstart test ./my-project
```

Expected output:

```text
Analyzing project: my-python-project
Docker image: python:3.12-slim
[1/3] Install dependencies .. PASSED
[2/3] Run tests ................ PASSED
[3/3] Check application ........ PASSED

----------------------------------------
SETUP TEST PASSED

Total steps:  3
Passed:       3
...
Reports:
  ./my-project/freshstart-report.md
  ./my-project/freshstart-report.json
```

See [configuration.md](configuration.md) for the full schema, and
[docker-security.md](docker-security.md) for the security model.
