from unittest.mock import patch, MagicMock
import json

from qa_framework_generator_ts.validators import smoke_validate


def _devserver_proc(alive=True, returncode=None):
    m = MagicMock()
    m.poll = MagicMock(return_value=None if alive else returncode)
    m.terminate = MagicMock()
    m.kill = MagicMock()
    m.wait = MagicMock(return_value=returncode if returncode is not None else 0)
    m.stdout = MagicMock()
    m.stderr = MagicMock()
    m.stdout.read = MagicMock(return_value="")
    m.stderr.read = MagicMock(return_value="")
    return m


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_disabled_returns_noop(popen, run, probe):
    results = smoke_validate("/tmp/out", target_app={}, enabled=False)
    assert len(results) == 1
    assert results[0].name == "smoke"
    assert results[0].passed is True
    assert "disabled" in results[0].output.lower()
    popen.assert_not_called()
    run.assert_not_called()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_happy_path(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"stats": {"unexpected": 0}, "suites": []}),
        stderr="",
    )
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
    )
    names = [r.name for r in results]
    assert "smoke" in names
    smoke = next(r for r in results if r.name == "smoke")
    assert smoke.passed is True
    popen.return_value.terminate.assert_called_once()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=None)
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_dev_server_unhealthy(popen, probe):
    popen.return_value = _devserver_proc(alive=True)
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
        health_timeout=1,
    )
    assert any(r.name == "dev_server_unhealthy" for r in results)
    popen.return_value.terminate.assert_called_once()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_tests_failed_yields_per_test_results(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.return_value = MagicMock(
        returncode=1,
        stdout=json.dumps({
            "stats": {"unexpected": 1},
            "suites": [{
                "specs": [{
                    "title": "assigns income",
                    "file": "specs/budget.spec.ts",
                    "tests": [{
                        "results": [{
                            "status": "failed",
                            "error": {"message": "locator timed out"},
                        }],
                    }],
                }],
            }],
        }),
        stderr="",
    )
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
    )
    test_failures = [r for r in results if r.name.startswith("test_failure:")]
    assert len(test_failures) == 1
    assert "assigns income" in test_failures[0].name
    assert "locator timed out" in test_failures[0].output


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_terminates_devserver_even_on_exception(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.side_effect = RuntimeError("playwright exploded")
    try:
        smoke_validate(
            "/tmp/out",
            target_app={
                "base_url": "http://localhost:5173",
                "start_command": "npm run dev",
                "start_cwd": "/tmp/app",
                "health_path": "/",
            },
            enabled=True,
        )
    except RuntimeError:
        pass
    popen.return_value.terminate.assert_called_once()
