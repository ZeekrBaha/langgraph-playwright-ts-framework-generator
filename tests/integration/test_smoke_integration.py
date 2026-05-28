"""End-to-end smoke step against tests/fixtures/tiny-vite-app.

Runs real subprocesses. Marked `slow` so it can be skipped in fast CI.
Requires Node 20+ and a one-time `npm install` in the fixture dir.
"""
import shutil
import subprocess
from pathlib import Path

import pytest


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tiny-vite-app"


@pytest.fixture(scope="module")
def fixture_app_installed():
    if not shutil.which("npm"):
        pytest.skip("npm not in PATH")
    if not (FIXTURE / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=FIXTURE, check=True, timeout=300)
    yield FIXTURE


@pytest.mark.slow
def test_dev_server_unhealthy_is_caught(fixture_app_installed, tmp_path):
    from qa_framework_generator_ts.validators import smoke_validate
    # Point at a port nothing serves
    results = smoke_validate(
        str(tmp_path),
        target_app={
            "base_url": "http://localhost:1",
            "start_command": "node -e 'setTimeout(()=>{},10000)'",
            "start_cwd": str(fixture_app_installed),
            "health_path": "/",
        },
        enabled=True,
        health_timeout=2,
    )
    assert any(r.name == "dev_server_unhealthy" for r in results)


@pytest.mark.slow
def test_dev_server_starts_and_health_probe_succeeds(fixture_app_installed):
    from qa_framework_generator_ts.validators import _http_probe, _wait_for_health
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=fixture_app_installed,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ok = _wait_for_health("http://localhost:5174", "/", timeout=30, proc=proc)
        assert ok is True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
