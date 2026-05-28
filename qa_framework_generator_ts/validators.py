from __future__ import annotations

import json
import shlex
import subprocess
import time
import urllib.error
import urllib.request
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


def _http_probe(url: str, timeout: float = 1.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except (urllib.error.URLError, OSError, ConnectionError):
        return None


def _wait_for_health(
    base_url: str,
    health_path: str,
    timeout: int,
    proc: subprocess.Popen,
) -> bool:
    deadline = time.monotonic() + timeout
    url = base_url.rstrip("/") + health_path
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False  # dev server died
        if _http_probe(url) is not None:
            return True
        time.sleep(0.5)
    return False


def _terminate(proc: subprocess.Popen, grace: float = 5.0) -> None:
    try:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)
    except ProcessLookupError:
        pass


def _parse_failures(report_json: str) -> list[ValidationResult]:
    failures: list[ValidationResult] = []
    try:
        report = json.loads(report_json)
    except json.JSONDecodeError:
        return [ValidationResult(
            name="smoke_unparseable_report",
            passed=False,
            output=_trim_output(report_json),
            fix_hint="playwright json report was malformed",
        )]
    for suite in report.get("suites", []) or []:
        for spec in suite.get("specs", []) or []:
            title = spec.get("title", "unknown")
            file = spec.get("file", "unknown")
            for t in spec.get("tests", []) or []:
                for r in t.get("results", []) or []:
                    if r.get("status") == "failed":
                        msg = (r.get("error") or {}).get("message", "")
                        failures.append(ValidationResult(
                            name=f"test_failure:{title}",
                            passed=False,
                            output=f"file={file}\n{_trim_output(msg)}",
                            fix_hint="fix locator/assertion to match the rendered UI",
                        ))
    return failures


def smoke_validate(
    output_dir: str,
    target_app: dict,
    enabled: bool,
    health_timeout: int = 30,
) -> list[ValidationResult]:
    if not enabled:
        return [ValidationResult(name="smoke", passed=True, output="disabled (no --smoke flag)")]

    base_url = target_app["base_url"]
    cmd = shlex.split(target_app["start_command"])
    cwd = target_app["start_cwd"]
    health_path = target_app["health_path"]

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        if not _wait_for_health(base_url, health_path, health_timeout, proc):
            return [ValidationResult(
                name="dev_server_unhealthy",
                passed=False,
                output=f"dev server did not respond at {base_url}{health_path} within {health_timeout}s",
                fix_hint="check start_command, start_cwd, health_path in target_app",
            )]

        run_result = subprocess.run(
            ["npx", "playwright", "test", "--reporter=json"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=600,
            env={"BASE_URL": base_url, **__import__("os").environ},
        )

        if run_result.returncode == 0:
            return [ValidationResult(name="smoke", passed=True, output="all tests passed")]

        failures = _parse_failures(run_result.stdout)
        if not failures:
            return [ValidationResult(
                name="smoke_crashed",
                passed=False,
                output=_trim_output(run_result.stderr or run_result.stdout),
                fix_hint="playwright exited non-zero with no parseable failures",
            )]
        return failures
    finally:
        _terminate(proc)
