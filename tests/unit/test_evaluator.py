from unittest.mock import patch, MagicMock

from qa_framework_generator_ts.evaluator import (
    evaluate_page_object,
    evaluate_spec,
    evaluate_generated_files,
    _PAGE_OBJECT_CRITERIA_TS,
    _SPEC_CRITERIA_TS,
)
from qa_framework_generator_ts.state import GeneratedFile


def test_page_object_criteria_lists_locator_methods():
    for m in ["getByRole", "getByLabel", "getByText", "getByTestId", "getByPlaceholder", "getByAltText", "getByTitle"]:
        assert m in _PAGE_OBJECT_CRITERIA_TS
    assert "page.locator" in _PAGE_OBJECT_CRITERIA_TS
    assert "waitForTimeout" in _PAGE_OBJECT_CRITERIA_TS


def test_spec_criteria_demands_web_first():
    assert "test.step" in _SPEC_CRITERIA_TS
    assert "await expect" in _SPEC_CRITERIA_TS
    assert "fixtures" in _SPEC_CRITERIA_TS.lower()


@patch("qa_framework_generator_ts.evaluator._make_geval")
def test_evaluate_page_object_passes_when_score_above_threshold(make_geval):
    metric = MagicMock()
    metric.score = 0.9
    metric.reason = "looks fine"
    make_geval.return_value = metric
    result = evaluate_page_object(
        GeneratedFile(path="src/pages/HomePage.ts", content="class HomePage {}", kind="typescript"),
        {"name": "HomePage"},
        threshold=0.7,
    )
    assert result.passed is True
    assert result.name == "eval_page_object_HomePage"


@patch("qa_framework_generator_ts.evaluator._make_geval")
def test_evaluate_page_object_fails_below_threshold(make_geval):
    metric = MagicMock()
    metric.score = 0.5
    metric.reason = "missing locators"
    make_geval.return_value = metric
    result = evaluate_page_object(
        GeneratedFile(path="src/pages/X.ts", content="class X {}", kind="typescript"),
        {"name": "X"},
        threshold=0.7,
    )
    assert result.passed is False
    assert "missing locators" in result.output


@patch("qa_framework_generator_ts.evaluator._make_geval")
def test_evaluate_generated_files_routes_by_path(make_geval):
    metric = MagicMock()
    metric.score = 0.9
    metric.reason = "ok"
    make_geval.return_value = metric
    files = [
        GeneratedFile(path="src/pages/BudgetPage.ts", content="class BudgetPage {}", kind="typescript"),
        GeneratedFile(path="specs/budget.spec.ts", content="test('x', async()=>{})", kind="typescript"),
        GeneratedFile(path="package.json", content="{}", kind="json"),  # ignored by evaluator
    ]
    cfg = {
        "pages": [{"name": "BudgetPage"}],
        "flows": [{"name": "Budget"}],
    }
    results = evaluate_generated_files(files, cfg, threshold=0.7)
    names = {r.name for r in results}
    assert "eval_page_object_BudgetPage" in names
    assert any(n.startswith("eval_spec_") for n in names)
    # package.json should not be evaluated
    assert not any("package.json" in r.output for r in results)
