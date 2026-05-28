from qa_framework_generator_ts.graph import (
    route_after_evaluation,
    route_after_static_validation,
    route_after_smoke_validation,
    route_after_review,
    route_after_repair,
    build_graph,
)
from qa_framework_generator_ts.state import GeneratorState, ValidationResult


def _state(results=None, **overrides):
    base = {
        "config_path": "examples/minimal.yaml",
        "max_repair_attempts": 3,
        "repair_attempts": 0,
    }
    base.update(overrides)
    s = GeneratorState(**base)
    if results:
        s.validation_results = results
    return s


def test_route_after_evaluation_proceeds_when_evals_pass():
    s = _state(results=[ValidationResult(name="eval_page_object_x", passed=True)])
    assert route_after_evaluation(s) == "write_files"


def test_route_after_evaluation_repairs_on_eval_fail():
    s = _state(results=[ValidationResult(name="eval_page_object_x", passed=False)])
    assert route_after_evaluation(s) == "repair"


def test_route_after_static_validation_proceeds_to_smoke():
    s = _state(results=[ValidationResult(name="tsc", passed=True)])
    assert route_after_static_validation(s) == "smoke_validate"


def test_route_after_smoke_validation_proceeds_to_review():
    s = _state(results=[ValidationResult(name="smoke", passed=True)])
    assert route_after_smoke_validation(s) == "review"


def test_route_after_review_proceeds_to_final_report_when_done():
    s = _state(status="done")
    assert route_after_review(s) == "final_report"


def test_route_after_repair_caps_attempts():
    s = _state(repair_attempts=3, max_repair_attempts=3)
    assert route_after_repair(s) == "final_report"


def test_route_after_repair_loops_under_cap():
    s = _state(repair_attempts=1, max_repair_attempts=3)
    assert route_after_repair(s) == "static_validate"


def test_build_graph_compiles_without_error():
    g = build_graph()
    assert g is not None


def test_final_report_failed_after_repair_exhaustion():
    """Repair exhausted, validation_results cleared, last_failures has truth → status failed."""
    from qa_framework_generator_ts.graph import final_report_node
    from qa_framework_generator_ts.state import GeneratorState, ValidationResult
    state = GeneratorState(
        config_path="examples/minimal.yaml",
        output_dir="/tmp/test-repair-exhaustion",
        project_name="x",
        target_package="x",
        repair_attempts=3,
        max_repair_attempts=3,
        validation_results=[],  # cleared by the last repair pass
        last_failures=[ValidationResult(name="tsc", passed=False, output="error TS2304")],
    )
    out = final_report_node(state)
    assert out["status"] == "failed"


def test_final_report_done_when_no_failures_and_no_repair_exhaustion():
    """Happy path: no failures, no repair history → status done."""
    from qa_framework_generator_ts.graph import final_report_node
    from qa_framework_generator_ts.state import GeneratorState, ValidationResult
    state = GeneratorState(
        config_path="examples/minimal.yaml",
        output_dir="/tmp/test-happy",
        project_name="x",
        target_package="x",
        repair_attempts=0,
        max_repair_attempts=3,
        validation_results=[ValidationResult(name="smoke", passed=True)],
    )
    out = final_report_node(state)
    assert out["status"] == "done"


def test_repair_node_saves_failures_to_last_failures():
    """repair_node must populate last_failures with the cleared failures."""
    from unittest.mock import patch
    from qa_framework_generator_ts.graph import repair_node
    from qa_framework_generator_ts.state import GeneratorState, GeneratedFile, ValidationResult

    state = GeneratorState(
        config_path="examples/minimal.yaml",
        output_dir="/tmp/test-repair-saves",
        generated_files=[GeneratedFile(path="src/x.ts", content="x", kind="typescript")],
        validation_results=[
            ValidationResult(name="tsc", passed=False, output="error TS2304"),
            ValidationResult(name="eslint", passed=True, output="ok"),
        ],
        repair_attempts=0,
        max_repair_attempts=3,
    )
    with patch("qa_framework_generator_ts.repair.repair_files") as repair_files, \
         patch("qa_framework_generator_ts.file_writer.write_files"):
        repair_files.return_value = state.generated_files
        out = repair_node(state)
    # Only failing results land in last_failures
    assert len(out["last_failures"]) == 1
    assert out["last_failures"][0].name == "tsc"
    assert out["validation_results"] == []  # cleared as before
