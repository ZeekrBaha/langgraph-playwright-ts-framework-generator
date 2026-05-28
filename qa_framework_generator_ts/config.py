from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, model_validator


RESERVED_ELEMENT_NAMES = {"page", "goto", "locator", "url", "name"}
DEFAULT_BROWSERS = ["chromium", "firefox", "webkit", "mobile-chrome"]


class RoleLocator(BaseModel):
    strategy: Literal["role"]
    role: str
    name: Optional[str] = None


class ValueLocator(BaseModel):
    strategy: Literal["testid", "label", "text", "placeholder", "altText", "title"]
    value: str


Locator = Union[RoleLocator, ValueLocator]


class Element(BaseModel):
    name: str
    locator: Locator

    @model_validator(mode="after")
    def _reserved(self) -> "Element":
        if self.name in RESERVED_ELEMENT_NAMES:
            raise ValueError(
                f"element name '{self.name}' is reserved; pick another. "
                f"Reserved: {sorted(RESERVED_ELEMENT_NAMES)}"
            )
        return self


class ActionParam(BaseModel):
    name: str
    type: Literal["string", "number", "boolean"]


class ActionStep(BaseModel):
    do: Literal["click", "fill", "select", "check", "uncheck", "hover", "press"]
    target: str
    value: Optional[str] = None


class Action(BaseModel):
    name: str
    params: list[ActionParam] = Field(default_factory=list)
    steps: list[ActionStep]


class Page(BaseModel):
    name: str
    url: str
    elements: list[Element]
    actions: list[Action] = Field(default_factory=list)


class FlowStep(BaseModel):
    page: str
    action: str
    args: dict = Field(default_factory=dict)


class FlowAssertion(BaseModel):
    on: str  # e.g. "HomePage.title"
    expect: Literal[
        "toBeVisible", "toBeHidden", "toHaveText", "toContainText",
        "toHaveValue", "toHaveCount", "toBeEnabled", "toBeDisabled",
    ]
    value: Optional[Union[str, int]] = None


class Flow(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)
    steps: list[FlowStep]
    assertions: list[FlowAssertion]


class TargetApp(BaseModel):
    name: str
    base_url: str
    start_command: str
    start_cwd: str
    health_path: str


class FrameworkConfig(BaseModel):
    project_name: str
    package_name: str
    output_dir: str
    target_app: TargetApp
    browsers: list[str] = Field(default_factory=lambda: list(DEFAULT_BROWSERS))
    pages: list[Page] = Field(min_length=1)
    flows: list[Flow] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_unique_and_refs(self) -> "FrameworkConfig":
        page_names = [p.name for p in self.pages]
        dups = {n for n in page_names if page_names.count(n) > 1}
        if dups:
            raise ValueError(f"duplicate page names: {sorted(dups)}")

        flow_names = [f.name for f in self.flows]
        flow_dups = {n for n in flow_names if flow_names.count(n) > 1}
        if flow_dups:
            raise ValueError(f"duplicate flow names: {sorted(flow_dups)}")

        page_index = {p.name: p for p in self.pages}
        for flow in self.flows:
            for step in flow.steps:
                if step.page not in page_index:
                    raise ValueError(
                        f"flow '{flow.name}' references undefined page '{step.page}'"
                    )
                page = page_index[step.page]
                if step.action != "goto" and step.action not in {a.name for a in page.actions}:
                    raise ValueError(
                        f"flow '{flow.name}' references undefined action "
                        f"'{step.action}' on page '{step.page}'"
                    )
            for assertion in flow.assertions:
                if "." not in assertion.on:
                    raise ValueError(
                        f"assertion 'on' must be 'PageName.elementName', got '{assertion.on}'"
                    )
                pname, ename = assertion.on.split(".", 1)
                if pname not in page_index:
                    raise ValueError(
                        f"assertion references undefined page '{pname}'"
                    )
                if ename not in {e.name for e in page_index[pname].elements}:
                    raise ValueError(
                        f"assertion references undefined element '{ename}' on '{pname}'"
                    )
        return self


def load_config(path: str) -> FrameworkConfig:
    raw = yaml.safe_load(Path(path).read_text())
    return FrameworkConfig(**raw)
