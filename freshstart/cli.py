"""Freshstart command-line interface.

Exit codes:

* ``0`` — all setup steps passed.
* ``1`` — one or more setup steps failed.
* ``2`` — invalid configuration or arguments.
* ``3`` — Docker or infrastructure error.
* ``4`` — execution timeout.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

import typer

from . import __version__
from .config.parser import ConfigError, find_config_file, parse_config
from .config.templates import generate_starter_yaml
from .config.validator import FreshstartConfig
from .docker.manager import DockerError, DockerManager
from .execution import Executor, StepResult
from .execution.analysis import analyze_results
from .reporting import (
    build_json_report,
    build_summary,
    generate_markdown_report,
    write_json_report,
    write_markdown_report,
)
from .utils.files import StagingStats, detect_project_language, stage_project

EXIT_OK = 0
EXIT_STEPS_FAILED = 1
EXIT_INVALID = 2
EXIT_DOCKER_ERROR = 3
EXIT_TIMEOUT = 4

app = typer.Typer(
    help="Freshstart: check that a project installs and sets up cleanly in a fresh environment.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _echo_error(message: str) -> None:
    typer.secho(f"ERROR: {message}", fg=typer.colors.RED, err=True)


def _resolve_config_path(project_dir: Path, config_path: str | None) -> Path | None:
    """Resolve the config file: an explicit ``--config`` first, else the default names."""
    if config_path:
        candidate = Path(config_path)
        if not candidate.is_absolute():
            candidate = project_dir / candidate
        if candidate.is_file():
            return candidate
        if Path(config_path).is_file():
            return Path(config_path).resolve()
        return None
    return find_config_file(project_dir)


def _make_step_printer(total: int):
    """Build a progress callback that prints one line per executed step."""
    counter = {"index": 0}

    def _print(result: StepResult) -> None:
        counter["index"] += 1
        typer.echo(f"[{counter['index']}/{total}] {result.step_name} ... {result.status}")

    return _print


def _warn_staging(stats: StagingStats) -> None:
    for line in stats.warning_lines():
        typer.echo(f"  {line}")


def _print_summary(summary, findings, md_path, json_path) -> None:
    overall = summary["overall_status"]
    color = typer.colors.GREEN if overall == "PASSED" else typer.colors.RED
    typer.secho(f"SETUP TEST {overall}", fg=color)
    typer.echo("")
    typer.echo(f"Total steps:  {summary['total_steps']}")
    typer.echo(f"Passed:       {summary['passed']}")
    typer.echo(f"Failed:       {summary['failed']}")
    typer.echo(f"Skipped:      {summary['skipped']}")
    typer.echo(f"Timed out:    {summary['timed_out']}")
    typer.echo(f"Duration:     {summary['duration_seconds']}s")
    if findings:
        typer.echo("")
        typer.echo("Main problem:")
        first = findings[0]
        typer.echo(f"  {first.message}")
        if first.suggestion:
            typer.echo(f"  Suggestion: {first.suggestion}")
    typer.echo("")
    typer.echo("Reports:")
    if md_path:
        typer.echo(f"  {md_path}")
    if json_path:
        typer.echo(f"  {json_path}")


def _exit_code_from_summary(summary) -> int:
    if summary["errors"]:
        return EXIT_DOCKER_ERROR
    if summary["timed_out"]:
        return EXIT_TIMEOUT
    if summary["failed"]:
        return EXIT_STEPS_FAILED
    return EXIT_OK


# ---------------------------------------------------------------------------
# Core test flow
# ---------------------------------------------------------------------------
def run_test(
    project_dir: str,
    config_path: str | None = None,
    allow_network: bool = False,
    report_dir: str | None = None,
) -> int:
    """Run the Freshstart test flow; returns the process exit code."""
    project_dir_path = Path(project_dir).resolve()

    if not project_dir_path.is_dir():
        _echo_error(f"Project directory not found: {project_dir_path}")
        return EXIT_INVALID

    found_config = _resolve_config_path(project_dir_path, config_path)
    if found_config is None:
        _echo_error(f"No configuration file found in {project_dir_path}.")
        typer.echo(f"Create one with: freshstart init {project_dir_path}")
        typer.echo(f"Or pass one explicitly: freshstart test {project_dir_path} --config <path>")
        return EXIT_INVALID

    try:
        config: FreshstartConfig = parse_config(found_config)
    except ConfigError as exc:
        _echo_error(str(exc))
        return EXIT_INVALID

    if allow_network:
        config.environment.allow_network = True

    # -- Docker availability checks ---------------------------------------
    manager = DockerManager()
    if not manager.docker_available():
        _echo_error("Docker was not found or is not usable.")
        typer.echo("Install Docker: https://docs.docker.com/get-docker/")
        typer.echo(
            "On Windows, ensure WSL 2 is enabled: https://learn.microsoft.com/windows/wsl/install"
        )
        return EXIT_DOCKER_ERROR
    if not manager.daemon_running():
        _echo_error("The Docker daemon is not running.")
        typer.echo("Start Docker Desktop (or the Docker Engine service) and try again.")
        return EXIT_DOCKER_ERROR
    try:
        manager.pull_image(config.environment.image)
    except DockerError as exc:
        _echo_error(f"Failed to pull image '{config.environment.image}': {exc}")
        return EXIT_DOCKER_ERROR

    # -- Stage, copy, and execute ------------------------------------------
    staging_dir: Path | None = None
    try:
        staging_dir = Path(tempfile.mkdtemp(prefix="freshstart-stage-"))
        stats = stage_project(project_dir_path, staging_dir)
        _warn_staging(stats)

        try:
            manager.create_container(
                image=config.environment.image,
                workdir=config.environment.workdir,
                memory_mb=config.execution.memory_mb,
                cpus=config.execution.cpus,
                network="bridge" if config.environment.allow_network else "none",
            )
            manager.copy_project(staging_dir, config.environment.workdir)
            manager.start_container()
        except DockerError as exc:
            _echo_error(f"Failed to prepare the container: {exc}")
            return EXIT_DOCKER_ERROR

        typer.echo(f"Analyzing project: {config.project.name}")
        typer.echo(f"Docker image: {config.environment.image}")
        executor = Executor(manager, config, on_step=_make_step_printer(len(config.steps)))
        started = time.monotonic()
        results = executor.execute()
        total_duration = time.monotonic() - started

        findings = analyze_results(results)
        summary = build_summary(results)
        environment_info = {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "docker_version": manager.server_version() or "unknown",
        }

        report_path = Path(report_dir) if report_dir else project_dir_path
        md_path = write_markdown_report(
            report_path / "freshstart-report.md",
            generate_markdown_report(
                config, results, findings, project_dir_path, environment_info, total_duration
            ),
        )
        json_path = write_json_report(
            report_path / "freshstart-report.json",
            build_json_report(
                config, results, findings, project_dir_path, environment_info, total_duration
            ),
        )
        _print_summary(summary, findings, md_path, json_path)
        return _exit_code_from_summary(summary)
    finally:
        try:
            manager.cleanup()
        except DockerError:
            pass
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
@app.callback(invoke_without_command=True)
def _callback(
    ctx: typer.Context,
    version: bool | None = typer.Option(None, "--version", help="Show the version and exit."),
) -> None:
    if version:
        typer.echo(f"freshstart {__version__}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("test")
def test_command(
    directory: str = typer.Argument(..., help="Path to the project directory to test."),
    config_path: str | None = typer.Option(
        None, "--config", help="Path to the .freshstart.yml configuration file."
    ),
    allow_network: bool = typer.Option(
        False, "--allow-network", help="Allow network access inside the container."
    ),
    report_dir: str | None = typer.Option(
        None, "--report-dir", help="Directory for the reports (default: project directory)."
    ),
) -> None:
    exit_code = run_test(
        directory, config_path=config_path, allow_network=allow_network, report_dir=report_dir
    )
    raise typer.Exit(code=exit_code)


@app.command("init")
def init_command(
    directory: str = typer.Argument(..., help="Project directory to initialize."),
) -> None:
    project_dir = Path(directory).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    target = project_dir / ".freshstart.yml"
    if target.exists():
        typer.echo(f"{target} already exists; not overwriting it.")
        return
    language = detect_project_language(project_dir)
    target.write_text(generate_starter_yaml(project_dir.name, language), encoding="utf-8")
    typer.echo(f"Created {target}")
    typer.echo(f"Edit it to describe your setup, then run: freshstart test {project_dir}")


@app.command("validate")
def validate_command(
    directory: str = typer.Argument(..., help="Project directory to validate."),
    config_path: str | None = typer.Option(
        None, "--config", help="Path to the .freshstart.yml configuration file."
    ),
) -> None:
    project_dir = Path(directory).resolve()
    if not project_dir.is_dir():
        _echo_error(f"Project directory not found: {project_dir}")
        raise typer.Exit(code=EXIT_INVALID)
    found = _resolve_config_path(project_dir, config_path)
    if found is None:
        _echo_error(
            f"No configuration file found in {project_dir}. Run: freshstart init {project_dir}"
        )
        raise typer.Exit(code=EXIT_INVALID)
    try:
        config = parse_config(found)
    except ConfigError as exc:
        _echo_error(str(exc))
        raise typer.Exit(code=EXIT_INVALID)
    typer.secho(f"OK: {found} is valid", fg=typer.colors.GREEN)
    typer.echo(f"  version: {config.version}")
    typer.echo(f"  project: {config.project.name}")
    typer.echo(f"  image: {config.environment.image}")
    typer.echo(f"  workdir: {config.environment.workdir}")
    typer.echo(f"  steps: {len(config.steps)}")
    for index, step in enumerate(config.steps, start=1):
        typer.echo(f"    {index}. {step.name}")
