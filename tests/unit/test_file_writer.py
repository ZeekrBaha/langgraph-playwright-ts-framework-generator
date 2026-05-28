from pathlib import Path

from qa_framework_generator_ts.file_writer import write_files, CLEANUP_IGNORE_PATTERNS
from qa_framework_generator_ts.state import GeneratedFile


def test_writes_files_to_output_dir(tmp_path):
    files = [GeneratedFile(path="src/a.ts", content="export const a = 1;", kind="typescript")]
    write_files(files, str(tmp_path), force=True)
    assert (tmp_path / "src" / "a.ts").read_text() == "export const a = 1;"


def test_cleanup_removes_stale_files(tmp_path):
    stale = tmp_path / "src" / "stale.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=True)
    assert not stale.exists()
    assert (tmp_path / "src" / "a.ts").exists()


def test_cleanup_preserves_ignored_paths(tmp_path):
    nm = tmp_path / "node_modules" / "x" / "index.js"
    nm.parent.mkdir(parents=True)
    nm.write_text("y")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=True)
    assert nm.exists()


def test_cleanup_disabled_keeps_stale(tmp_path):
    stale = tmp_path / "src" / "stale.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=False)
    assert stale.exists()


def test_ignore_patterns_include_expected_dirs():
    assert "node_modules" in CLEANUP_IGNORE_PATTERNS
    assert ".git" in CLEANUP_IGNORE_PATTERNS
    assert "playwright-report" in CLEANUP_IGNORE_PATTERNS
    assert "test-results" in CLEANUP_IGNORE_PATTERNS
