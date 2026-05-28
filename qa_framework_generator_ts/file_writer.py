from __future__ import annotations

from pathlib import Path
from typing import Iterable

from qa_framework_generator_ts.state import GeneratedFile


CLEANUP_IGNORE_PATTERNS = {
    "node_modules",
    ".git",
    ".venv",
    "playwright-report",
    "test-results",
    "__pycache__",
    ".pytest_cache",
}


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    for part in rel.parts:
        if part in CLEANUP_IGNORE_PATTERNS:
            return True
    return False


def _existing_managed_files(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return found
    for p in root.rglob("*"):
        if p.is_file() and not _is_ignored(p, root):
            found.append(p)
    return found


def write_files(
    files: Iterable[GeneratedFile],
    output_dir: str,
    force: bool = False,
    cleanup: bool = True,
) -> None:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    new_paths = {(root / f.path).resolve() for f in files}

    if cleanup:
        for existing in _existing_managed_files(root):
            if existing.resolve() not in new_paths:
                existing.unlink()
        # remove empty dirs (excluding the root) — bottom-up
        for d in sorted([p for p in root.rglob("*") if p.is_dir()], reverse=True):
            if _is_ignored(d, root):
                continue
            try:
                d.rmdir()
            except OSError:
                pass

    for f in files:
        dest = root / f.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            raise FileExistsError(f"{dest} exists and force=False")
        dest.write_text(f.content)
