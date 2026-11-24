"""Small file-staging helpers.

Freshstart copies the user's project into a disposable container.  This
module implements the staging step with strict safety rules:

* Excluded directories (``.git``, caches, virtual environments, ...) are
  skipped by default.
* Secret-looking files (``.env``, keys, certificates, ...) are never copied.
* Symlinks that resolve outside the project directory are never followed.
* Files above a size limit or past a total-size limit are skipped and
  reported.
"""

from __future__ import annotations

import fnmatch
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_FILE_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB per file
DEFAULT_MAX_PROJECT_SIZE_BYTES = 512 * 1024 * 1024  # 512 MB total

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".idea",
        ".vscode",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        "__pycache__",
        ".venv",
        "venv",
        "bower_components",
        "secrets",
        "dist",
        "build",
    }
)

SECRET_FILE_NAMES = frozenset({".env", ".npmrc", ".netrc", ".pgpass", ".gitconfig"})

SECRET_FILE_PATTERNS = (
    "*.pem",
    "*.key",
    "*.ppk",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "*.credentials",
    "*_credentials",
)


@dataclass
class StagingStats:
    """What was staged and what was skipped during staging."""

    files: list[str] = field(default_factory=list)
    excluded_directories: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    skipped_symlinks: list[str] = field(default_factory=list)
    oversized_files: list[str] = field(default_factory=list)
    truncated_files: list[str] = field(default_factory=list)

    def warning_lines(self) -> list[str]:
        """Human-readable warnings about anything that was skipped."""
        lines: list[str] = []
        if self.excluded_files:
            lines.append(f"Excluded secret-like files: {', '.join(self.excluded_files)}")
        if self.skipped_symlinks:
            lines.append(f"Skipped symlinks: {', '.join(self.skipped_symlinks)}")
        if self.oversized_files:
            lines.append(f"Skipped oversized files: {', '.join(self.oversized_files)}")
        if self.truncated_files:
            lines.append(f"Project size limit reached; skipped: {', '.join(self.truncated_files)}")
        return lines


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_secret_name(name: str) -> bool:
    if name in SECRET_FILE_NAMES:
        return True
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_FILE_PATTERNS)


def stage_project(
    project_dir: Path,
    destination: Path,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    max_total_size: int = DEFAULT_MAX_PROJECT_SIZE_BYTES,
) -> StagingStats:
    """Copy *project_dir* into *destination*, honoring exclusion rules.

    Symlinks are never followed out of the project directory, and
    secret-like files are never copied.  Returns a :class:`StagingStats`
    describing what was copied and what was skipped.
    """
    project_dir = Path(project_dir).resolve()
    destination = Path(destination)
    if not project_dir.is_dir():
        raise ValueError(f"Project directory does not exist: {project_dir}")
    destination.mkdir(parents=True, exist_ok=True)

    stats = StagingStats()
    total_bytes = 0

    for root, dirnames, filenames in os.walk(project_dir, followlinks=False):
        root_path = Path(root)

        # Prune directories that should not be copied (mutating while
        # iterating a sorted copy of the names).
        for dirname in sorted(dirnames):
            dir_path = root_path / dirname
            relative = dir_path.relative_to(project_dir)
            if dirname in EXCLUDED_DIRECTORIES or _is_secret_name(dirname):
                stats.excluded_directories.append(relative.as_posix())
                dirnames.remove(dirname)
                continue
            if dir_path.is_symlink():
                target = Path(os.path.realpath(dir_path))
                if not _is_within(target, project_dir):
                    stats.skipped_symlinks.append(relative.as_posix())
                    dirnames.remove(dirname)
            else:
                (destination / relative).mkdir(parents=True, exist_ok=True)

        for filename in sorted(filenames):
            file_path = root_path / filename
            relative = file_path.relative_to(project_dir)
            relative_posix = relative.as_posix()
            dest_path = destination / relative
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.is_symlink():
                target = Path(os.path.realpath(file_path))
                if not _is_within(target, project_dir):
                    stats.skipped_symlinks.append(relative_posix)
                    continue
                file_path = target
            if _is_secret_name(file_path.name):
                stats.excluded_files.append(relative_posix)
                continue
            if not file_path.is_file():
                stats.skipped_symlinks.append(relative_posix)
                continue
            try:
                size = file_path.stat().st_size
            except OSError:
                stats.skipped_symlinks.append(relative_posix)
                continue
            if size > max_file_size:
                stats.oversized_files.append(relative_posix)
                continue
            if total_bytes + size > max_total_size:
                stats.truncated_files.append(relative_posix)
                continue
            shutil.copy2(file_path, dest_path)
            stats.files.append(relative_posix)
            total_bytes += size

    return stats


def detect_project_language(project_dir: Path) -> str:
    """Best-effort detection of the project language, for starter configs."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return "unknown"
    try:
        names = {entry.name for entry in project_dir.iterdir()}
    except OSError:
        return "unknown"
    if "package.json" in names or any(
        name.endswith((".js", ".jsx", ".ts", ".tsx")) for name in names
    ):
        return "node"
    if any(name in names for name in ("requirements.txt", "pyproject.toml")) or any(
        name.endswith(".py") for name in names
    ):
        return "python"
    return "unknown"
