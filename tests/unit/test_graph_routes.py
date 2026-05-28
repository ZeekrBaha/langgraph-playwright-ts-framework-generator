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
