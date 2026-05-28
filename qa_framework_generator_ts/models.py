from __future__ import annotations

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


class TestCaseOutput(BaseModel):
    describe: str
    test_name: str
    tags: list[str] = Field(default_factory=list)
    used_fixtures: list[str]
    steps: list[dict]
    assertions: list[dict]


class ReviewOutput(BaseModel):
    passed: bool
    findings: list[str] = Field(default_factory=list)
