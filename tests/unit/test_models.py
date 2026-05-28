import pytest
from pydantic import ValidationError

from qa_framework_generator_ts.models import (
    RequirementsOutput,
    BlueprintOutput,
    PageObjectOutput,
    TestCaseOutput,
    ReviewOutput,
)


def test_requirements_round_trip():
    r = RequirementsOutput(goals=["g1"], coverage=["c1"], risks=["r1"])
    assert r.goals == ["g1"]


def test_blueprint_round_trip():
    b = BlueprintOutput(
        page_classes=["BudgetPage"],
        spec_files=["budget.spec.ts"],
        fixtures=["budgetPage"],
        tags=["smoke"],
    )
    assert b.fixtures == ["budgetPage"]


def test_page_object_output_requires_class_and_elements():
    p = PageObjectOutput(
        class_name="BudgetPage",
        url="/",
        elements=[{"name": "x", "locator": {"strategy": "testid", "value": "x"}}],
        actions=[],
    )
    assert p.class_name == "BudgetPage"


def test_test_case_output_round_trip():
    t = TestCaseOutput(
        describe="HomeFlow",
        test_name="navigates",
        tags=["smoke"],
        used_fixtures=["homePage"],
        steps=[{"label": "open", "body": "await homePage.goto();"}],
        assertions=[{"subject": "homePage.title", "expect": "toBeVisible", "value": None}],
    )
    assert t.tags == ["smoke"]


def test_review_output_required_fields():
    r = ReviewOutput(passed=True, findings=[])
    assert r.passed is True
