from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field


class RequirementsOutput(BaseModel):
    goals: list[str]
    coverage: list[str]
    risks: list[str]


class BlueprintOutput(BaseModel):
    page_classes: list[str]
    spec_files: list[str]
    fixtures: list[str]
    tags: list[str] = Field(default_factory=list)


class PageObjectOutput(BaseModel):
    class_name: str
    url: str
    elements: list[dict]
    actions: list[dict]


class TestStep(BaseModel):
    """One step inside a spec's test body.

    Renders as `await test.step('{label}', async () => { {body} });`
    The body is a verbatim TypeScript statement (the fixture-method call).
    """
    label: str
    body: str


class TestAssertion(BaseModel):
    """One web-first assertion in a spec.

    Renders as `await expect({subject}).{expect}({value});`
    `value` is omitted from the call when None (e.g. for `toBeVisible`).
    """
    subject: str
    expect: str
    value: Optional[Union[str, int]] = None


class TestCaseOutput(BaseModel):
    describe: str
    test_name: str
    tags: list[str] = Field(default_factory=list)
    used_fixtures: list[str]
    steps: list[TestStep]
    assertions: list[TestAssertion]


class ReviewOutput(BaseModel):
    passed: bool
    findings: list[str] = Field(default_factory=list)
