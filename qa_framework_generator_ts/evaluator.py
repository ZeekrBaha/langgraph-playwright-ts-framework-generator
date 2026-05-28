from __future__ import annotations

import os
import re

from qa_framework_generator_ts.state import GeneratedFile, ValidationResult


try:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase
    try:
        from deepeval.test_case import SingleTurnParams as _EvalParams
    except ImportError:
        from deepeval.test_case import LLMTestCaseParams as _EvalParams  # type: ignore[no-redef]
    _DEEPEVAL_AVAILABLE = True
except ImportError:
    _DEEPEVAL_AVAILABLE = False  # type: ignore[assignment]


_DEFAULT_THRESHOLD = 0.7

_PAGE_OBJECT_CRITERIA_TS = (
    "The TypeScript Playwright page object class must satisfy ALL of:\n"
    "1. Class name exactly matches the page name from the spec.\n"
    "2. Constructor accepts `page: Page` as a private readonly field.\n"
    "3. Every YAML element appears as a readonly Locator field.\n"
    "4. Locators are built from getByRole, getByLabel, getByText, getByTestId, "
    "getByPlaceholder, getByAltText, or getByTitle — never page.locator() with CSS or XPath.\n"
    "5. Every YAML action exists as an async method with matching parameters.\n"
    "6. No page.waitForTimeout, no setTimeout, no manual sleeps.\n"
    "7. Methods use locator actions directly; no `await locator.waitFor()` before clicks."
)

_SPEC_CRITERIA_TS = (
    "The TypeScript Playwright spec file must satisfy ALL of:\n"
    "1. Imports `test` and `expect` from the project's fixtures module, not from @playwright/test.\n"
    "2. Every YAML step appears, wrapped in `await test.step('...', async () => { ... })`.\n"
    "3. Every YAML assertion is a web-first `await expect(locator).toX(...)` call.\n"
    "4. No expect(await locator.isVisible()).toBe(true) anti-pattern.\n"
    "5. No floating promises (every async call awaited).\n"
    "6. No page.waitForTimeout.\n"
    "7. Test tags from YAML appear via test.describe.configure({ tag })."
)


def _make_geval(name: str, criteria: str, threshold: float):
    return GEval(
        name=name,
        criteria=criteria,
        evaluation_params=[_EvalParams.INPUT, _EvalParams.ACTUAL_OUTPUT],
        threshold=threshold,
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
    )


def evaluate_page_object(
    file: GeneratedFile,
    page_spec: dict,
    threshold: float = _DEFAULT_THRESHOLD,
) -> ValidationResult:
    name = page_spec.get("name", "unknown")
    metric = _make_geval("PageObjectQualityTS", _PAGE_OBJECT_CRITERIA_TS, threshold)
    metric.measure(LLMTestCase(input=str(page_spec), actual_output=file.content))
    return ValidationResult(
        name=f"eval_page_object_{name}",
        passed=metric.score >= threshold,
        output=f"score={metric.score:.2f} | {metric.reason}",
        fix_hint=f"improve {name} page object: {metric.reason}",
    )


def evaluate_spec(
    file: GeneratedFile,
    flow_spec: dict,
    threshold: float = _DEFAULT_THRESHOLD,
) -> ValidationResult:
    name = flow_spec.get("name", "unknown")
    metric = _make_geval("SpecQualityTS", _SPEC_CRITERIA_TS, threshold)
    metric.measure(LLMTestCase(input=str(flow_spec), actual_output=file.content))
    return ValidationResult(
        name=f"eval_spec_{name}",
        passed=metric.score >= threshold,
        output=f"score={metric.score:.2f} | {metric.reason}",
        fix_hint=f"improve {name} spec: {metric.reason}",
    )


def evaluate_generated_files(
    files: list[GeneratedFile],
    config_data: dict,
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    page_specs = {p["name"]: p for p in config_data.get("pages", [])}
    flow_specs = {f["name"]: f for f in config_data.get("flows", [])}

    for f in files:
        m = re.match(r"^src/pages/(.+)\.ts$", f.path)
        if m and m.group(1) in page_specs:
            results.append(evaluate_page_object(f, page_specs[m.group(1)], threshold))
            continue
        m = re.match(r"^specs/(.+)\.spec\.ts$", f.path)
        if m:
            for fname, fspec in flow_specs.items():
                if fname.lower() == m.group(1).lower():
                    results.append(evaluate_spec(f, fspec, threshold))
                    break
    return results
