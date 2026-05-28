from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GeneratedFile(BaseModel):
    path: str
    content: str
    kind: Literal["typescript", "json", "yaml", "markdown", "config", "other"] = "other"


class ValidationResult(BaseModel):
    name: str
    passed: bool
    output: str = ""
    fix_hint: str = ""


class GeneratorState(BaseModel):
    config_path: str
    output_dir: Optional[str] = None

    config_data: dict = Field(default_factory=dict)
    project_name: str = ""
    target_package: str = ""

    requirements: dict = Field(default_factory=dict)
    blueprint: dict = Field(default_factory=dict)

    generated_files: list[GeneratedFile] = Field(default_factory=list)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    last_failures: list[ValidationResult] = Field(default_factory=list)

    repair_attempts: int = 0
    max_repair_attempts: int = 3
    eval_threshold: float = 0.7

    smoke_enabled: bool = False
    smoke_log: Optional[str] = None

    status: str = "pending"
