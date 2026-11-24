"""File staging tests."""

import sys

import pytest

from freshstart.utils.files import (
    detect_project_language,
    stage_project,
)


def make_project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    return project


def test_copies_regular_files(tmp_path):
    project = make_project(tmp_path)
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("print('hi')")
    staging = tmp_path / "staging"
    stats = stage_project(project, staging)
    assert (staging / "src" / "main.py").is_file()
    assert "src/main.py" in stats.files


def test_excludes_git_and_caches(tmp_path):
    project = make_project(tmp_path)
    (project / ".git").mkdir()
    (project / ".git" / "HEAD").write_text("ref: refs/heads/main")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"\x00")
    (project / ".mypy_cache").mkdir()
    (project / "src").mkdir()
    (project / "src" / "a.py").write_text("x = 1")
    staging = tmp_path / "staging"
    stage_project(project, staging)
    assert not (staging / ".git").exists()
    assert not (staging / "__pycache__").exists()
    assert not (staging / ".mypy_cache").exists()
    assert (staging / "src" / "a.py").exists()
    assert (project / ".git" / "HEAD") in [project / ".git" / "HEAD"]  # source untouched


def test_excludes_secret_files(tmp_path):
    project = make_project(tmp_path)
    (project / ".env").write_text("SECRET=1")
    (project / ".npmrc").write_text("//registry.npmjs.org/:_authToken=abc")
    (project / "id_rsa").write_text("PRIVATE")
    (project / "server.pem").write_text("CERT")
    staging = tmp_path / "staging"
    stats = stage_project(project, staging)
    assert not (staging / ".env").exists()
    assert not (staging / ".npmrc").exists()
    assert not (staging / "id_rsa").exists()
    assert not (staging / "server.pem").exists()
    assert len(stats.excluded_files) >= 4


def test_oversized_file_skipped(tmp_path):
    project = make_project(tmp_path)
    (project / "big.bin").write_bytes(b"x" * 100)
    staging = tmp_path / "staging"
    stats = stage_project(project, staging, max_file_size=50)
    assert not (staging / "big.bin").exists()
    assert stats.oversized_files == ["big.bin"]


def test_total_size_limit_truncates(tmp_path):
    project = make_project(tmp_path)
    (project / "a.txt").write_text("a" * 30)
    (project / "b.txt").write_text("b" * 30)
    staging = tmp_path / "staging"
    stats = stage_project(project, staging, max_file_size=100, max_total_size=50)
    assert (staging / "a.txt").exists()
    assert not (staging / "b.txt").exists()
    assert stats.truncated_files == ["b.txt"]


def test_symlink_outside_project_skipped(tmp_path):
    if sys.platform == "win32":
        pytest.skip("symlink creation may require privileges on Windows")
    project = make_project(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside")
    link = project / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted here")
    staging = tmp_path / "staging"
    stats = stage_project(project, staging)
    assert not (staging / "link.txt").exists()
    assert any("link.txt" in path for path in stats.skipped_symlinks)


def test_symlink_inside_project_copied(tmp_path):
    if sys.platform == "win32":
        pytest.skip("symlink creation may require privileges on Windows")
    project = make_project(tmp_path)
    (project / "real.txt").write_text("real content")
    link = project / "link.txt"
    try:
        link.symlink_to(project / "real.txt")
    except OSError:
        pytest.skip("symlinks not permitted here")
    staging = tmp_path / "staging"
    stage_project(project, staging)
    copied = staging / "link.txt"
    assert copied.exists()
    assert copied.read_text() == "real content"


def test_detect_project_language(tmp_path):
    project = tmp_path / "empty"
    project.mkdir()
    assert detect_project_language(project) == "unknown"
    (project / "package.json").write_text("{}")
    assert detect_project_language(project) == "node"
    (project / "package.json").unlink()
    (project / "app.py").write_text("print(1)")
    assert detect_project_language(project) == "python"
