# Freshstart Docker Security

Freshstart creates a **disposable Docker container** per test run. It is a
development and CI tool: it wants a reasonably isolated environment, not an
absolute security boundary against hostile code. Freshstart is designed to be
used with projects you already trust; it does not claim to make untrusted
uploaded code safe to execute.

## Defaults that keep things contained

- Network is **disabled by default** (`--network none`). Install packages and
  run the configured steps; pass `--allow-network` (or set `allow_network: true`)
  only when you need internet access, for example for `pip install`.
- Resource limits: `--cpus` (default 1.0), `--memory` (default 512 MB),
  `--pids-limit` (default 256).
- Capability restrictions: `--cap-drop ALL` and `--security-opt no-new-privileges`.
- No host filesystem mounts. The project is **copied** into the container; the
  host filesystem is never mounted.
- The Docker socket is not mounted into the container, and the container is
  never started privileged.

## What is excluded from the copy

The project directory is staged into a temporary folder before copying:

- `.git`, `node_modules`, virtual environments (`venv`, `.venv`),
  `__pycache__`, caches (`.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`,
  `.ipynb_checkpoints`), and a few other build outputs.
- Secret-like files are not copied: `.env`, `.npmrc`, `.netrc`, `.pgpass`,
  `*.pem`, `*.key`, `*.ppk`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, and
  similar names. This is best-effort hygiene, not a guarantee — users should
  not rely on it for real secrets.
- Symlinks that resolve outside the project directory are skipped.
- Per-file and total size limits are applied by default (4 MB/file,
  512 MB total); oversized files are skipped and reported.

## Output hygiene

- stdout/stderr are capped per step (default 30,000 characters) and are
  truncated with a note.
- Secrets in captured output are redacted with common patterns (API keys,
  tokens, passwords, GitHub/AWS/Slack tokens, private key blocks) in the
  generated reports. This is best-effort.

## Cleanup

- The container is stopped and removed after the run, including on failures
  and timeouts, and the staging directory is deleted.
- No images are removed by Freshstart (image pulls are cached by Docker).

## Things we intentionally do not promise

- A hostile project can still try to break out or mine crypto from inside the
  container; Docker containers are isolates but not absolute sandboxes.
- Without `--allow-network`, some legitimate setup steps (like
  `npm install` or `pip install`) will fail.

## Recommendations for CI usage

- Use a pinned Docker image (`image: python:3.12-slim`, not `python:latest`).
- Run on ephemeral CI runners.
- Add a timeout to the workflow step so a hanging step cannot run forever.
- When testing pull requests from forks, do not use `pull_request_target` to
  run arbitrary project code, and document the risk to maintainers.
