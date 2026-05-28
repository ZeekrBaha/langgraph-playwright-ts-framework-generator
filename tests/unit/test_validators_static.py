from unittest.mock import patch, MagicMock

from qa_framework_generator_ts.validators import (
    validate_static,
    _trim_output,
)


def test_trim_output_short_passes_through():
    assert _trim_output("hello") == "hello"


def test_trim_output_long_keeps_head_and_tail():
    long = "A" * 2000 + "B" * 2000
    trimmed = _trim_output(long, head=1500, tail=1500)
    assert trimmed.startswith("A" * 100)
    assert trimmed.endswith("B" * 100)
    assert "[truncated]" in trimmed


def _ok():
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


def _fail(stderr: str):
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_all_pass(run):
    run.side_effect = [_ok(), _ok(), _ok()]
    results = validate_static("/tmp/out")
    assert [r.name for r in results] == ["tsc", "eslint", "playwright_list"]
    assert all(r.passed for r in results)
    assert run.call_count == 3


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_short_circuits_on_tsc_failure(run):
    run.side_effect = [_fail("error TS2304: Cannot find name 'x'"), _ok(), _ok()]
    results = validate_static("/tmp/out")
    assert results[0].name == "tsc"
    assert results[0].passed is False
    assert "TS2304" in results[0].output
    # eslint and playwright_list should still be present but marked skipped
    assert results[1].name == "eslint"
    assert results[1].passed is True
    assert "skipped" in results[1].output.lower()
    assert run.call_count == 1


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_timeout(run):
    import subprocess
    run.side_effect = subprocess.TimeoutExpired(cmd=["tsc"], timeout=120)
    results = validate_static("/tmp/out")
    assert results[0].name == "tsc_timeout"
    assert results[0].passed is False
