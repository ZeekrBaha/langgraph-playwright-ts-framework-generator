from __future__ import annotations

import subprocess
from pathlib import Path

from qa_framework_generator_ts.state import ValidationResult


_STATIC_TIMEOUT = 120  # seconds


def _trim_output(text: str, head: int = 1500, tail: int = 1500) -> str:
    if len(text) <= head + tail:
        return text
    return f"{text[:head]}\n…[truncated]…\n{text[-tail:]}"


def _run(cmd: list[str], cwd: str, timeout: int = _STATIC_TIMEOUT) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _skipped(name: str, reason: str) -> ValidationResult:
    return ValidationResult(name=name, passed=True, output=f"skipped: {reason}")


def validate_static(output_dir: str) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    steps = [
        ("tsc", ["npx", "tsc", "--noEmit", "-p", "tsconfig.json"]),
        ("eslint", ["npx", "eslint", "."]),
        ("playwright_list", ["npx", "playwright", "test", "--list"]),
    ]

    short_circuit_reason: str | None = None
    for name, cmd in steps:
        if short_circuit_reason is not None:
            results.append(_skipped(name, short_circuit_reason))
            continue
        try:
            code, stdout, stderr = _run(cmd, output_dir)
        except subprocess.TimeoutExpired:
            results.append(ValidationResult(
                name=f"{name}_timeout",
                passed=False,
                output=f"timeout after {_STATIC_TIMEOUT}s",
                fix_hint="reduce scope or investigate hangs",
            ))
            short_circuit_reason = f"earlier step '{name}' timed out"
            continue
        except FileNotFoundError as exc:
            results.append(ValidationResult(
                name=name,
                passed=False,
                output=f"command not found: {exc}",
                fix_hint=f"ensure {cmd[0]} is installed in PATH",
            ))
            short_circuit_reason = f"earlier step '{name}' missing toolchain"
            continue

        if code == 0:
            results.append(ValidationResult(name=name, passed=True, output="ok"))
        else:
            combined = (stderr or "") + ("\n---stdout---\n" + stdout if stdout else "")
            results.append(ValidationResult(
                name=name,
                passed=False,
                output=_trim_output(combined),
                fix_hint=f"fix {name} errors and rerun",
            ))
            short_circuit_reason = f"earlier step '{name}' failed"

    return results
