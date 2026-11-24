# Contributing to Freshstart

Thanks for contributing! This project uses:

- Python 3.11+, pytest, Ruff (linting), and mypy (type checking).
- The layout is documented in `README.md` under *Repository structure*; the
  main packages are `freshstart/` (application code), `tests/` (automated
  tests), `examples/` (sample projects), and `docs/` (documentation).

## Development setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

Docker-dependent integration tests are skipped automatically when Docker is
unavailable.

## Code style

- Run `ruff check .` (and `ruff format` if you want canonical formatting).
- Run `mypy freshstart` before opening a PR.
- Keep functions small and typed; use type hints throughout.

## Reporting bugs

Please use [the issue tracker](https://github.com/your-org/freshstart/issues)
and include the command you ran, your operating system, the Docker version,
and a snippet of the relevant `freshstart-report.md` if applicable.

## Submitting changes

1. Fork the repository.
2. Create a branch for your change.
3. Make your change and add/adjust tests.
4. Run the test suite and linters.
5. Submit a pull request with a clear description.
