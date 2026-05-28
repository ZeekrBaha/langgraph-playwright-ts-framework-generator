"""Full graph end-to-end with LLM mocked to canned outputs.

Uses real subprocesses where possible (file writes) but skips tsc/eslint/playwright
because those depend on `npm install` which is out of scope for this fast test.
We validate file *existence* and *contract compliance* (no banned patterns) instead.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock


def _canned_llm_responses():
    from qa_framework_generator_ts.models import (
        RequirementsOutput, BlueprintOutput, PageObjectOutput, TestCaseOutput, ReviewOutput,
    )
    return {
        RequirementsOutput: RequirementsOutput(goals=["g"], coverage=["c"], risks=["r"]),
        BlueprintOutput: BlueprintOutput(
            page_classes=["HomePage"], spec_files=["homeflow.spec.ts"],
            fixtures=["homePage"], tags=["smoke"],
        ),
        PageObjectOutput: PageObjectOutput(
            class_name="HomePage", url="/",
            elements=[{"name": "heading", "locator": {"strategy": "role", "role": "heading", "name": "Welcome"}}],
            actions=[],
        ),
        TestCaseOutput: TestCaseOutput(
            describe="HomeFlow", test_name="navigates", tags=["smoke"],
            used_fixtures=["homePage"],
            steps=[{"label": "open home", "body": "await homePage.goto();"}],
            assertions=[{"subject": "homePage.heading", "expect": "toBeVisible", "value": None}],
        ),
        ReviewOutput: ReviewOutput(passed=True, findings=[]),
    }


def _structured_invoker(canned: dict):
    """Returns a callable that mimics ChatOpenAI(...).with_structured_output(M).invoke(...)."""
    def fake_with_structured_output(model_cls, **_kwargs):
        m = MagicMock()
        m.invoke = MagicMock(return_value=canned[model_cls])
        return m
    return fake_with_structured_output


@patch("qa_framework_generator_ts.validators.validate_static")
@patch("qa_framework_generator_ts.evaluator.evaluate_generated_files")
@patch("qa_framework_generator_ts.graph.get_openai_chat_model", create=True)
def test_e2e_minimal_produces_compliant_framework(get_llm, eval_fn, vs_fn, tmp_path):
    # Force all evaluators to pass — we are checking templates, not LLM grading.
    from qa_framework_generator_ts.state import ValidationResult
    eval_fn.return_value = [ValidationResult(name="eval_page_object_HomePage", passed=True)]
    vs_fn.return_value = [
        ValidationResult(name="tsc", passed=True),
        ValidationResult(name="eslint", passed=True),
        ValidationResult(name="playwright_list", passed=True),
    ]

    canned = _canned_llm_responses()
    llm = MagicMock()
    llm.with_structured_output = MagicMock(side_effect=_structured_invoker(canned))
    get_llm.return_value = llm

    # Need to patch llm import sites used by graph nodes too.
    with patch("qa_framework_generator_ts.llm.get_openai_chat_model", return_value=llm), \
         patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False):
        from qa_framework_generator_ts.graph import build_graph
        graph = build_graph()
        final = graph.invoke({
            "config_path": "tests/fixtures/valid_minimal.yaml",
            "output_dir": str(tmp_path / "out"),
            "smoke_enabled": False,
        })

    status = final["status"] if isinstance(final, dict) else final.status
    assert status == "done", f"final status={status}, results={final.get('validation_results')}"

    out = tmp_path / "out"
    # Required structural files
    for required in [
        "package.json",
        "tsconfig.json",
        "playwright.config.ts",
        "eslint.config.js",
        ".github/workflows/test.yml",
        "src/pages/HomePage.ts",
        "src/fixtures.ts",
        "specs/homeflow.spec.ts",
        "README.md",
        "GENERATION_REPORT.md",
    ]:
        assert (out / required).exists(), f"missing {required}"

    # Contract compliance — no forbidden patterns
    for ts in out.rglob("*.ts"):
        body = ts.read_text()
        assert "page.waitForTimeout" not in body, f"{ts} contains waitForTimeout"
        assert "expect(await " not in body, f"{ts} uses non-web-first assertion"

    home = (out / "src/pages/HomePage.ts").read_text()
    assert "getByRole('heading'" in home
    assert "page.locator(" not in home

    spec = (out / "specs/homeflow.spec.ts").read_text()
    assert "from '../src/fixtures'" in spec
    assert "test.step" in spec
    assert "@smoke" in spec
