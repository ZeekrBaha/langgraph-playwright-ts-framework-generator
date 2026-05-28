# LangGraph Playwright/TypeScript Framework Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python LangGraph-orchestrated generator that takes a YAML spec and emits a production-quality Playwright + TypeScript end-to-end test framework, with BudgetZero as the canonical demo target.

**Architecture:** Mirrors the existing `langgraph-selenium-testng-framework-generator` topology (12-node graph: load_config → requirements → blueprint → render_static → generate_pages → evaluate → write_files → static_validate → smoke_validate → review → final_report, with a repair loop). The LangGraph skeleton is reused; node bodies, templates, validators, and DeepEval criteria are rewritten for the TS/Playwright target. YAML is the single source of truth for routes, elements, and flows.

**Tech Stack:** Python 3.12+, LangGraph, OpenAI structured outputs, Pydantic v2, Jinja2, DeepEval, pytest, uv. Output stack: TypeScript, Playwright 1.60+, ESLint, Vite (target apps).

**Repo root for all paths in this plan:** `~/Desktop/llm-ai-projects/langgraph-playwright-ts-framework-generator/`. Already exists with `docs/superpowers/specs/2026-05-28-langgraph-playwright-ts-generator-design.md` committed.

**Reference repos (read-only):**
- `~/Desktop/llm-ai-projects/langgraph-selenium-testng-framework-generator/` — the Java/Selenium generator we are paralleling
- `~/Desktop/llm-ai-projects/budgetzero-web/` — canonical test target (React 19 + Vite + Convex)

---

## Task 1: Scaffold The Project

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `qa_framework_generator_ts/__init__.py`
- Create: `qa_framework_generator_ts/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "qa-framework-generator-ts"
version = "0.1.0"
description = "LangGraph-orchestrated Playwright/TypeScript test framework generator"
requires-python = ">=3.12"
dependencies = [
  "langgraph>=0.2.0",
  "openai>=1.50.0",
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "jinja2>=3.1",
  "deepeval>=1.0",
  "python-dotenv>=1.0",
  "click>=8.1",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-mock>=3.12",
  "syrupy>=4.6",
]

[project.scripts]
qa-gen-ts = "qa_framework_generator_ts.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["qa_framework_generator_ts"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
*.egg-info/
dist/
build/
.deepeval/
playwright-ts-framework-output/
node_modules/
```

- [ ] **Step 3: Create .env.example**

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
```

- [ ] **Step 4: Create empty __init__ files**

`qa_framework_generator_ts/__init__.py`:
```python
"""LangGraph-orchestrated Playwright/TypeScript test framework generator."""
__version__ = "0.1.0"
```

`qa_framework_generator_ts/__main__.py`:
```python
from qa_framework_generator_ts.cli import main

if __name__ == "__main__":
    main()
```

`tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`: empty files.

- [ ] **Step 5: Install dependencies**

Run: `cd ~/Desktop/llm-ai-projects/langgraph-playwright-ts-framework-generator && uv venv && uv pip install -e ".[dev]"`

Expected: install completes; `.venv/` created.

- [ ] **Step 6: Verify package imports**

Run: `uv run python -c "import qa_framework_generator_ts; print(qa_framework_generator_ts.__version__)"`

Expected: `0.1.0`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore .env.example qa_framework_generator_ts/ tests/
git commit -m "chore: scaffold project — pyproject, env, package skeleton

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: GeneratorState Pydantic Model

**Files:**
- Create: `qa_framework_generator_ts/state.py`
- Create: `tests/unit/test_state.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_state.py`:
```python
from qa_framework_generator_ts.state import GeneratedFile, GeneratorState, ValidationResult


def test_generator_state_defaults():
    state = GeneratorState(config_path="examples/minimal.yaml")
    assert state.config_path == "examples/minimal.yaml"
    assert state.output_dir is None
    assert state.generated_files == []
    assert state.validation_results == []
    assert state.repair_attempts == 0
    assert state.max_repair_attempts == 3
    assert state.eval_threshold == 0.7
    assert state.smoke_enabled is False
    assert state.smoke_log is None
    assert state.status == "pending"


def test_generated_file_round_trip():
    f = GeneratedFile(path="src/foo.ts", content="export {};", kind="typescript")
    assert f.path == "src/foo.ts"
    assert f.kind == "typescript"


def test_validation_result_failure_carries_hint():
    r = ValidationResult(name="tsc", passed=False, output="error TS2304", fix_hint="define the symbol")
    assert r.passed is False
    assert r.fix_hint == "define the symbol"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'qa_framework_generator_ts.state'`

- [ ] **Step 3: Implement state.py**

`qa_framework_generator_ts/state.py`:
```python
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

    repair_attempts: int = 0
    max_repair_attempts: int = 3
    eval_threshold: float = 0.7

    smoke_enabled: bool = False
    smoke_log: Optional[str] = None

    status: str = "pending"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_state.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/state.py tests/unit/test_state.py
git commit -m "feat(state): GeneratorState, GeneratedFile, ValidationResult

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: Config Schema (YAML → Pydantic)

**Files:**
- Create: `qa_framework_generator_ts/config.py`
- Create: `tests/unit/test_config.py`
- Create: `tests/fixtures/valid_minimal.yaml`
- Create: `tests/fixtures/invalid_css_locator.yaml`
- Create: `tests/fixtures/invalid_dup_page.yaml`
- Create: `tests/fixtures/invalid_flow_ref.yaml`

- [ ] **Step 1: Create fixture YAML files**

`tests/fixtures/valid_minimal.yaml`:
```yaml
project_name: demo-e2e
package_name: demo
output_dir: ./out
target_app:
  name: Demo
  base_url: http://localhost:5173
  start_command: npm run dev
  start_cwd: ../demo-web
  health_path: /
browsers:
  - chromium
pages:
  - name: HomePage
    url: /
    elements:
      - name: title
        locator: { strategy: role, role: heading, name: "Welcome" }
    actions:
      - name: openMenu
        params: []
        steps:
          - { do: click, target: title }
flows:
  - name: HomeFlow
    tags: [smoke]
    steps:
      - { page: HomePage, action: goto }
    assertions:
      - { on: HomePage.title, expect: toBeVisible }
```

`tests/fixtures/invalid_css_locator.yaml`: same as above but replace the `locator` line with:
```yaml
        locator: { strategy: css, value: ".title" }
```

`tests/fixtures/invalid_dup_page.yaml`: same as `valid_minimal.yaml` but duplicate the `HomePage` block under `pages:` so the page name appears twice.

`tests/fixtures/invalid_flow_ref.yaml`: same as `valid_minimal.yaml` but change the flow's step to `{ page: NoSuchPage, action: goto }`.

- [ ] **Step 2: Write failing tests**

`tests/unit/test_config.py`:
```python
import pytest
from pydantic import ValidationError

from qa_framework_generator_ts.config import load_config


def test_loads_minimal_yaml():
    cfg = load_config("tests/fixtures/valid_minimal.yaml")
    assert cfg.project_name == "demo-e2e"
    assert cfg.package_name == "demo"
    assert cfg.browsers == ["chromium"]
    assert len(cfg.pages) == 1
    assert cfg.pages[0].name == "HomePage"
    assert cfg.pages[0].elements[0].locator.strategy == "role"


def test_rejects_css_locator():
    with pytest.raises(ValidationError) as exc:
        load_config("tests/fixtures/invalid_css_locator.yaml")
    assert "strategy" in str(exc.value)


def test_rejects_duplicate_page_name():
    with pytest.raises(ValidationError) as exc:
        load_config("tests/fixtures/invalid_dup_page.yaml")
    assert "duplicate" in str(exc.value).lower() or "HomePage" in str(exc.value)


def test_rejects_flow_referencing_undefined_page():
    with pytest.raises(ValidationError) as exc:
        load_config("tests/fixtures/invalid_flow_ref.yaml")
    assert "NoSuchPage" in str(exc.value)


def test_defaults_browsers_when_omitted(tmp_path):
    yaml_content = """
project_name: x
package_name: x
output_dir: ./out
target_app:
  name: X
  base_url: http://localhost:5173
  start_command: npm run dev
  start_cwd: ../x
  health_path: /
pages:
  - name: P
    url: /
    elements:
      - name: e
        locator: { strategy: testid, value: e }
    actions: []
flows:
  - name: F
    tags: []
    steps:
      - { page: P, action: goto }
    assertions: []
"""
    f = tmp_path / "x.yaml"
    f.write_text(yaml_content)
    cfg = load_config(str(f))
    assert cfg.browsers == ["chromium", "firefox", "webkit", "mobile-chrome"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement config.py**

`qa_framework_generator_ts/config.py`:
```python
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
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add qa_framework_generator_ts/config.py tests/unit/test_config.py tests/fixtures/*.yaml
git commit -m "feat(config): YAML schema with cross-ref validation

- Locator strategies constrained to testid/role/label/text/placeholder/altText/title
- Reject duplicates, undefined references, reserved names
- Default browsers when omitted

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: File Writer With Cleanup

**Files:**
- Create: `qa_framework_generator_ts/file_writer.py`
- Create: `tests/unit/test_file_writer.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_file_writer.py`:
```python
from pathlib import Path

from qa_framework_generator_ts.file_writer import write_files, CLEANUP_IGNORE_PATTERNS
from qa_framework_generator_ts.state import GeneratedFile


def test_writes_files_to_output_dir(tmp_path):
    files = [GeneratedFile(path="src/a.ts", content="export const a = 1;", kind="typescript")]
    write_files(files, str(tmp_path), force=True)
    assert (tmp_path / "src" / "a.ts").read_text() == "export const a = 1;"


def test_cleanup_removes_stale_files(tmp_path):
    stale = tmp_path / "src" / "stale.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=True)
    assert not stale.exists()
    assert (tmp_path / "src" / "a.ts").exists()


def test_cleanup_preserves_ignored_paths(tmp_path):
    nm = tmp_path / "node_modules" / "x" / "index.js"
    nm.parent.mkdir(parents=True)
    nm.write_text("y")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=True)
    assert nm.exists()


def test_cleanup_disabled_keeps_stale(tmp_path):
    stale = tmp_path / "src" / "stale.ts"
    stale.parent.mkdir(parents=True)
    stale.write_text("old")
    files = [GeneratedFile(path="src/a.ts", content="x", kind="typescript")]
    write_files(files, str(tmp_path), force=True, cleanup=False)
    assert stale.exists()


def test_ignore_patterns_include_expected_dirs():
    assert "node_modules" in CLEANUP_IGNORE_PATTERNS
    assert ".git" in CLEANUP_IGNORE_PATTERNS
    assert "playwright-report" in CLEANUP_IGNORE_PATTERNS
    assert "test-results" in CLEANUP_IGNORE_PATTERNS
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_file_writer.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement file_writer.py**

`qa_framework_generator_ts/file_writer.py`:
```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from qa_framework_generator_ts.state import GeneratedFile


CLEANUP_IGNORE_PATTERNS = {
    "node_modules",
    ".git",
    ".venv",
    "playwright-report",
    "test-results",
    "__pycache__",
    ".pytest_cache",
}


def _is_ignored(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    for part in rel.parts:
        if part in CLEANUP_IGNORE_PATTERNS:
            return True
    return False


def _existing_managed_files(root: Path) -> list[Path]:
    found: list[Path] = []
    if not root.exists():
        return found
    for p in root.rglob("*"):
        if p.is_file() and not _is_ignored(p, root):
            found.append(p)
    return found


def write_files(
    files: Iterable[GeneratedFile],
    output_dir: str,
    force: bool = False,
    cleanup: bool = True,
) -> None:
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

    new_paths = {(root / f.path).resolve() for f in files}

    if cleanup:
        for existing in _existing_managed_files(root):
            if existing.resolve() not in new_paths:
                existing.unlink()
        # remove empty dirs (excluding the root) — bottom-up
        for d in sorted([p for p in root.rglob("*") if p.is_dir()], reverse=True):
            if _is_ignored(d, root):
                continue
            try:
                d.rmdir()
            except OSError:
                pass

    for f in files:
        dest = root / f.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not force:
            raise FileExistsError(f"{dest} exists and force=False")
        dest.write_text(f.content)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_file_writer.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/file_writer.py tests/unit/test_file_writer.py
git commit -m "feat(file_writer): write with cleanup honoring ignore patterns

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Static Templates + Renderer (Framework Skeleton)

**Files:**
- Create: `qa_framework_generator_ts/renderer.py`
- Create: `qa_framework_generator_ts/templates/ts/package.json.j2`
- Create: `qa_framework_generator_ts/templates/ts/tsconfig.json.j2`
- Create: `qa_framework_generator_ts/templates/ts/playwright.config.ts.j2`
- Create: `qa_framework_generator_ts/templates/ts/eslint.config.js.j2`
- Create: `qa_framework_generator_ts/templates/ts/gitignore.j2`
- Create: `qa_framework_generator_ts/templates/ts/ci-workflow.yml.j2`
- Create: `qa_framework_generator_ts/templates/ts/helpers-selectors.ts.j2`
- Create: `qa_framework_generator_ts/templates/ts/helpers-money.ts.j2`
- Create: `qa_framework_generator_ts/templates/ts/README.md.j2`
- Create: `tests/unit/test_renderer_static.py`

- [ ] **Step 1: Write the templates**

`qa_framework_generator_ts/templates/ts/package.json.j2`:
```jinja
{
  "name": "{{ package_name }}",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:ui": "playwright test --ui",
    "test:headed": "playwright test --headed",
    "lint": "eslint ."
  },
  "devDependencies": {
    "@playwright/test": "^1.60.0",
    "@typescript-eslint/eslint-plugin": "^8.0.0",
    "@typescript-eslint/parser": "^8.0.0",
    "eslint": "^9.0.0",
    "typescript": "^5.5.0"
  }
}
```

`qa_framework_generator_ts/templates/ts/tsconfig.json.j2`:
```jinja
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "types": ["node"]
  },
  "include": ["src", "specs", "playwright.config.ts"]
}
```

`qa_framework_generator_ts/templates/ts/playwright.config.ts.j2`:
```jinja
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [['github'], ['html']] : 'list',
  use: {
    baseURL: process.env.BASE_URL ?? '{{ target_app.base_url }}',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
{% for b in browsers %}
{% if b == 'chromium' %}    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
{% elif b == 'firefox' %}    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
{% elif b == 'webkit' %}    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
{% elif b == 'mobile-chrome' %}    { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
{% elif b == 'mobile-safari' %}    { name: 'mobile-safari', use: { ...devices['iPhone 13'] } },
{% endif %}
{% endfor %}
  ],
});
```

`qa_framework_generator_ts/templates/ts/eslint.config.js.j2`:
```jinja
import tseslint from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';

export default [
  {
    files: ['**/*.ts'],
    languageOptions: { parser: tsParser, parserOptions: { project: './tsconfig.json' } },
    plugins: { '@typescript-eslint': tseslint },
    rules: {
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/await-thenable': 'error',
      'no-restricted-syntax': [
        'error',
        {
          selector: "CallExpression[callee.property.name='waitForTimeout']",
          message: 'page.waitForTimeout is forbidden; use web-first assertions.',
        },
      ],
    },
  },
];
```

`qa_framework_generator_ts/templates/ts/gitignore.j2`:
```jinja
node_modules/
playwright-report/
test-results/
.env
*.log
dist/
```

`qa_framework_generator_ts/templates/ts/ci-workflow.yml.j2`:
```jinja
name: e2e
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npx playwright install --with-deps {{ browsers | select('in', ['chromium','firefox','webkit']) | list | join(' ') }}
      - run: npx playwright test --shard=${{ '{{' }} matrix.shard {{ '}}' }}/4
        env:
          BASE_URL: {{ target_app.base_url }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report-shard-${{ '{{' }} matrix.shard {{ '}}' }}
          path: playwright-report/
```

`qa_framework_generator_ts/templates/ts/helpers-selectors.ts.j2`:
```jinja
// Typed selector tokens — re-exported from page objects for spec-level reuse.
export const TESTID = {
{% for p in pages %}
{% for el in p.elements %}
{% if el.locator.strategy == 'testid' %}  {{ p.name }}_{{ el.name }}: '{{ el.locator.value }}',
{% endif %}
{% endfor %}
{% endfor %}
} as const;
```

`qa_framework_generator_ts/templates/ts/helpers-money.ts.j2`:
```jinja
export function parseMoney(text: string): number {
  const cleaned = text.replace(/[^0-9.\-]/g, '');
  return Number.parseFloat(cleaned);
}

export function formatMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}
```

`qa_framework_generator_ts/templates/ts/README.md.j2`:
```jinja
# {{ project_name }}

Generated Playwright/TypeScript end-to-end suite for **{{ target_app.name }}**.

## Run

```bash
npm install
npx playwright install --with-deps
npm test
```

## Pages
{% for p in pages %}
- `pages/{{ p.name }}.ts` — `{{ p.url }}`
{% endfor %}

## Flows
{% for f in flows %}
- `specs/{{ f.name | lower }}.spec.ts`  (tags: {{ f.tags | join(', ') or 'none' }})
{% endfor %}
```

- [ ] **Step 2: Write failing tests**

`tests/unit/test_renderer_static.py`:
```python
from qa_framework_generator_ts.config import load_config
from qa_framework_generator_ts.renderer import render_static_templates


def test_renders_full_static_skeleton():
    cfg = load_config("tests/fixtures/valid_minimal.yaml")
    files = render_static_templates(cfg)
    paths = {f.path for f in files}
    assert "package.json" in paths
    assert "tsconfig.json" in paths
    assert "playwright.config.ts" in paths
    assert "eslint.config.js" in paths
    assert ".gitignore" in paths
    assert ".github/workflows/test.yml" in paths
    assert "src/helpers/selectors.ts" in paths
    assert "src/helpers/money.ts" in paths
    assert "README.md" in paths


def test_playwright_config_contains_base_url():
    cfg = load_config("tests/fixtures/valid_minimal.yaml")
    files = render_static_templates(cfg)
    pw = next(f for f in files if f.path == "playwright.config.ts")
    assert "http://localhost:5173" in pw.content
    assert "'chromium'" in pw.content


def test_playwright_config_locks_best_practice_defaults():
    cfg = load_config("tests/fixtures/valid_minimal.yaml")
    files = render_static_templates(cfg)
    pw = next(f for f in files if f.path == "playwright.config.ts")
    assert "fullyParallel: true" in pw.content
    assert "trace: 'on-first-retry'" in pw.content
    assert "video: 'retain-on-failure'" in pw.content
    assert "screenshot: 'only-on-failure'" in pw.content


def test_eslint_config_forbids_waitfortimeout():
    cfg = load_config("tests/fixtures/valid_minimal.yaml")
    files = render_static_templates(cfg)
    es = next(f for f in files if f.path == "eslint.config.js")
    assert "waitForTimeout" in es.content
    assert "no-floating-promises" in es.content
```

- [ ] **Step 3: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_renderer_static.py -v`
Expected: FAIL — no renderer module.

- [ ] **Step 4: Implement renderer.py**

`qa_framework_generator_ts/renderer.py`:
```python
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from qa_framework_generator_ts.config import FrameworkConfig
from qa_framework_generator_ts.state import GeneratedFile


_TEMPLATES_DIR = Path(__file__).parent / "templates" / "ts"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def render_static_templates(cfg: FrameworkConfig) -> list[GeneratedFile]:
    env = _env()
    ctx = cfg.model_dump()
    pairs = [
        ("package.json.j2", "package.json", "json"),
        ("tsconfig.json.j2", "tsconfig.json", "json"),
        ("playwright.config.ts.j2", "playwright.config.ts", "typescript"),
        ("eslint.config.js.j2", "eslint.config.js", "config"),
        ("gitignore.j2", ".gitignore", "other"),
        ("ci-workflow.yml.j2", ".github/workflows/test.yml", "yaml"),
        ("helpers-selectors.ts.j2", "src/helpers/selectors.ts", "typescript"),
        ("helpers-money.ts.j2", "src/helpers/money.ts", "typescript"),
        ("README.md.j2", "README.md", "markdown"),
    ]
    files: list[GeneratedFile] = []
    for tpl_name, out_path, kind in pairs:
        rendered = env.get_template(tpl_name).render(**ctx)
        files.append(GeneratedFile(path=out_path, content=rendered, kind=kind))  # type: ignore[arg-type]
    return files
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_renderer_static.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add qa_framework_generator_ts/renderer.py qa_framework_generator_ts/templates/ tests/unit/test_renderer_static.py
git commit -m "feat(renderer): static framework templates — config, CI, helpers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: LLM-Output Templates (Page Object, Fixtures, Spec)

**Files:**
- Create: `qa_framework_generator_ts/templates/ts/page-object.ts.j2`
- Create: `qa_framework_generator_ts/templates/ts/fixtures.ts.j2`
- Create: `qa_framework_generator_ts/templates/ts/spec.ts.j2`
- Modify: `qa_framework_generator_ts/renderer.py`
- Create: `tests/unit/test_renderer_dynamic.py`

- [ ] **Step 1: Write the templates**

`qa_framework_generator_ts/templates/ts/page-object.ts.j2`:
```jinja
import { Page, Locator } from '@playwright/test';

export class {{ class_name }} {
  constructor(private readonly page: Page) {}

{% for el in elements %}
{% if el.locator.strategy == 'testid' %}
  readonly {{ el.name }}: Locator = this.page.getByTestId('{{ el.locator.value }}');
{% elif el.locator.strategy == 'role' %}
{% if el.locator.name %}
  readonly {{ el.name }}: Locator = this.page.getByRole('{{ el.locator.role }}', { name: '{{ el.locator.name }}' });
{% else %}
  readonly {{ el.name }}: Locator = this.page.getByRole('{{ el.locator.role }}');
{% endif %}
{% elif el.locator.strategy == 'label' %}
  readonly {{ el.name }}: Locator = this.page.getByLabel('{{ el.locator.value }}');
{% elif el.locator.strategy == 'text' %}
  readonly {{ el.name }}: Locator = this.page.getByText('{{ el.locator.value }}');
{% elif el.locator.strategy == 'placeholder' %}
  readonly {{ el.name }}: Locator = this.page.getByPlaceholder('{{ el.locator.value }}');
{% elif el.locator.strategy == 'altText' %}
  readonly {{ el.name }}: Locator = this.page.getByAltText('{{ el.locator.value }}');
{% elif el.locator.strategy == 'title' %}
  readonly {{ el.name }}: Locator = this.page.getByTitle('{{ el.locator.value }}');
{% endif %}
{% endfor %}

  async goto(): Promise<void> {
    await this.page.goto('{{ url }}');
  }

{% for action in actions %}
  async {{ action.name }}({% for p in action.params %}{{ p.name }}: {{ p.type }}{% if not loop.last %}, {% endif %}{% endfor %}): Promise<void> {
{% for step in action.steps %}
{% if step.do == 'click' %}
    await this.{{ step.target }}.click();
{% elif step.do == 'fill' %}
    await this.{{ step.target }}.fill(String({{ step.value | replace('{', '${') if '{' in step.value else step.value | tojson }}));
{% elif step.do == 'check' %}
    await this.{{ step.target }}.check();
{% elif step.do == 'uncheck' %}
    await this.{{ step.target }}.uncheck();
{% elif step.do == 'hover' %}
    await this.{{ step.target }}.hover();
{% elif step.do == 'press' %}
    await this.{{ step.target }}.press({{ step.value | tojson }});
{% elif step.do == 'select' %}
    await this.{{ step.target }}.selectOption({{ step.value | tojson }});
{% endif %}
{% endfor %}
  }

{% endfor %}
}
```

`qa_framework_generator_ts/templates/ts/fixtures.ts.j2`:
```jinja
import { test as base, expect } from '@playwright/test';
{% for p in pages %}
import { {{ p.name }} } from './pages/{{ p.name }}';
{% endfor %}

type Fixtures = {
{% for p in pages %}
  {{ p.name[0] | lower }}{{ p.name[1:] }}: {{ p.name }};
{% endfor %}
};

export const test = base.extend<Fixtures>({
{% for p in pages %}
  {{ p.name[0] | lower }}{{ p.name[1:] }}: async ({ page }, use) => {
    await use(new {{ p.name }}(page));
  },
{% endfor %}
});

export { expect };
```

`qa_framework_generator_ts/templates/ts/spec.ts.j2`:
```jinja
import { test, expect } from '../src/fixtures';

{% if tags %}
test.describe.configure({ tag: [{% for t in tags %}'@{{ t }}'{% if not loop.last %}, {% endif %}{% endfor %}] });
{% endif %}

test.describe('{{ describe }}', () => {
  test('{{ test_name }}', async ({ {% for fx in used_fixtures %}{{ fx }}{% if not loop.last %}, {% endif %}{% endfor %} }) => {
{% for step in steps %}
    await test.step('{{ step.label }}', async () => {
      {{ step.body }}
    });
{% endfor %}

{% for a in assertions %}
    await expect({{ a.subject }}).{{ a.expect }}({% if a.value is not none %}{{ a.value | tojson }}{% endif %});
{% endfor %}
  });
});
```

- [ ] **Step 2: Extend renderer.py with three new functions**

Add to `qa_framework_generator_ts/renderer.py`:
```python
def render_page_object(
    class_name: str,
    url: str,
    elements: list[dict],
    actions: list[dict],
) -> str:
    env = _env()
    return env.get_template("page-object.ts.j2").render(
        class_name=class_name,
        url=url,
        elements=elements,
        actions=actions,
    )


def render_fixtures(pages: list[dict]) -> str:
    env = _env()
    return env.get_template("fixtures.ts.j2").render(pages=pages)


def render_spec(
    describe: str,
    test_name: str,
    tags: list[str],
    used_fixtures: list[str],
    steps: list[dict],
    assertions: list[dict],
) -> str:
    env = _env()
    return env.get_template("spec.ts.j2").render(
        describe=describe,
        test_name=test_name,
        tags=tags,
        used_fixtures=used_fixtures,
        steps=steps,
        assertions=assertions,
    )
```

- [ ] **Step 3: Write failing tests**

`tests/unit/test_renderer_dynamic.py`:
```python
from qa_framework_generator_ts.renderer import render_page_object, render_fixtures, render_spec


def test_page_object_uses_get_by_role():
    out = render_page_object(
        class_name="HomePage",
        url="/",
        elements=[
            {"name": "heading", "locator": {"strategy": "role", "role": "heading", "name": "Welcome"}},
            {"name": "tid", "locator": {"strategy": "testid", "value": "ready"}},
        ],
        actions=[],
    )
    assert "class HomePage" in out
    assert "constructor(private readonly page: Page)" in out
    assert "getByRole('heading', { name: 'Welcome' })" in out
    assert "getByTestId('ready')" in out
    assert "async goto(): Promise<void>" in out
    assert "page.locator(" not in out
    assert "waitForTimeout" not in out


def test_page_object_renders_action_methods():
    out = render_page_object(
        class_name="P",
        url="/x",
        elements=[{"name": "btn", "locator": {"strategy": "testid", "value": "b"}}],
        actions=[{
            "name": "press",
            "params": [],
            "steps": [{"do": "click", "target": "btn", "value": None}],
        }],
    )
    assert "async press(): Promise<void>" in out
    assert "await this.btn.click();" in out


def test_fixtures_extends_base_test():
    out = render_fixtures(pages=[{"name": "BudgetPage"}, {"name": "TransactionsPage"}])
    assert "import { test as base, expect } from '@playwright/test';" in out
    assert "import { BudgetPage } from './pages/BudgetPage';" in out
    assert "export const test = base.extend<Fixtures>" in out
    assert "budgetPage: async ({ page }, use) =>" in out
    assert "await use(new BudgetPage(page));" in out
    assert "export { expect };" in out


def test_spec_wraps_steps_in_test_step():
    out = render_spec(
        describe="HomeFlow",
        test_name="navigates",
        tags=["smoke"],
        used_fixtures=["homePage"],
        steps=[{"label": "open home", "body": "await homePage.goto();"}],
        assertions=[{"subject": "homePage.title", "expect": "toBeVisible", "value": None}],
    )
    assert "import { test, expect } from '../src/fixtures';" in out
    assert "@smoke" in out
    assert "await test.step('open home'" in out
    assert "await homePage.goto();" in out
    assert "await expect(homePage.title).toBeVisible();" in out
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_renderer_dynamic.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/renderer.py qa_framework_generator_ts/templates/ts/{page-object,fixtures,spec}.ts.j2 tests/unit/test_renderer_dynamic.py
git commit -m "feat(renderer): page-object/fixtures/spec templates with structural contract

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Static Validators (tsc, eslint, playwright list)

**Files:**
- Create: `qa_framework_generator_ts/validators.py`
- Create: `tests/unit/test_validators_static.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_validators_static.py`:
```python
from unittest.mock import patch, MagicMock

from qa_framework_generator_ts.validators import (
    validate_static,
    _trim_output,
)


def test_trim_output_short_passes_through():
    assert _trim_output("hello") == "hello"


def test_trim_output_long_keeps_head_and_tail():
    long = "A" * 2000 + "B" * 2000
    trimmed = _trim_output(long, head=1500, tail=1500)
    assert trimmed.startswith("A" * 100)
    assert trimmed.endswith("B" * 100)
    assert "[truncated]" in trimmed


def _ok():
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


def _fail(stderr: str):
    m = MagicMock()
    m.returncode = 1
    m.stdout = ""
    m.stderr = stderr
    return m


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_all_pass(run):
    run.side_effect = [_ok(), _ok(), _ok()]
    results = validate_static("/tmp/out")
    assert [r.name for r in results] == ["tsc", "eslint", "playwright_list"]
    assert all(r.passed for r in results)
    assert run.call_count == 3


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_short_circuits_on_tsc_failure(run):
    run.side_effect = [_fail("error TS2304: Cannot find name 'x'"), _ok(), _ok()]
    results = validate_static("/tmp/out")
    assert results[0].name == "tsc"
    assert results[0].passed is False
    assert "TS2304" in results[0].output
    # eslint and playwright_list should still be present but marked skipped
    assert results[1].name == "eslint"
    assert results[1].passed is True
    assert "skipped" in results[1].output.lower()
    assert run.call_count == 1


@patch("qa_framework_generator_ts.validators.subprocess.run")
def test_static_validate_timeout(run):
    import subprocess
    run.side_effect = subprocess.TimeoutExpired(cmd=["tsc"], timeout=120)
    results = validate_static("/tmp/out")
    assert results[0].name == "tsc_timeout"
    assert results[0].passed is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_validators_static.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement validators.py**

`qa_framework_generator_ts/validators.py`:
```python
from __future__ import annotations

import subprocess
from pathlib import Path

from qa_framework_generator_ts.state import ValidationResult


_STATIC_TIMEOUT = 120  # seconds


def _trim_output(text: str, head: int = 1500, tail: int = 1500) -> str:
    if len(text) <= head + tail:
        return text
    return f"{text[:head]}\n…[truncated]…\n{text[-tail:]}"


def _run(cmd: list[str], cwd: str, timeout: int = _STATIC_TIMEOUT) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _skipped(name: str, reason: str) -> ValidationResult:
    return ValidationResult(name=name, passed=True, output=f"skipped: {reason}")


def validate_static(output_dir: str) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    steps = [
        ("tsc", ["npx", "tsc", "--noEmit", "-p", "tsconfig.json"]),
        ("eslint", ["npx", "eslint", "."]),
        ("playwright_list", ["npx", "playwright", "test", "--list"]),
    ]

    short_circuit_reason: str | None = None
    for name, cmd in steps:
        if short_circuit_reason is not None:
            results.append(_skipped(name, short_circuit_reason))
            continue
        try:
            code, stdout, stderr = _run(cmd, output_dir)
        except subprocess.TimeoutExpired:
            results.append(ValidationResult(
                name=f"{name}_timeout",
                passed=False,
                output=f"timeout after {_STATIC_TIMEOUT}s",
                fix_hint="reduce scope or investigate hangs",
            ))
            short_circuit_reason = f"earlier step '{name}' timed out"
            continue
        except FileNotFoundError as exc:
            results.append(ValidationResult(
                name=name,
                passed=False,
                output=f"command not found: {exc}",
                fix_hint=f"ensure {cmd[0]} is installed in PATH",
            ))
            short_circuit_reason = f"earlier step '{name}' missing toolchain"
            continue

        if code == 0:
            results.append(ValidationResult(name=name, passed=True, output="ok"))
        else:
            combined = (stderr or "") + ("\n---stdout---\n" + stdout if stdout else "")
            results.append(ValidationResult(
                name=name,
                passed=False,
                output=_trim_output(combined),
                fix_hint=f"fix {name} errors and rerun",
            ))
            short_circuit_reason = f"earlier step '{name}' failed"

    return results
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_validators_static.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/validators.py tests/unit/test_validators_static.py
git commit -m "feat(validators): tsc + eslint + playwright list, short-circuit on failure

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: Smoke Validator (Live Dev Server + Playwright Run)

**Files:**
- Modify: `qa_framework_generator_ts/validators.py`
- Create: `tests/unit/test_validators_smoke.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_validators_smoke.py`:
```python
from unittest.mock import patch, MagicMock
import json

from qa_framework_generator_ts.validators import smoke_validate


def _devserver_proc(alive=True, returncode=None):
    m = MagicMock()
    m.poll = MagicMock(return_value=None if alive else returncode)
    m.terminate = MagicMock()
    m.kill = MagicMock()
    m.wait = MagicMock(return_value=returncode if returncode is not None else 0)
    m.stdout = MagicMock()
    m.stderr = MagicMock()
    m.stdout.read = MagicMock(return_value="")
    m.stderr.read = MagicMock(return_value="")
    return m


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_disabled_returns_noop(popen, run, probe):
    results = smoke_validate("/tmp/out", target_app={}, enabled=False)
    assert len(results) == 1
    assert results[0].name == "smoke"
    assert results[0].passed is True
    assert "disabled" in results[0].output.lower()
    popen.assert_not_called()
    run.assert_not_called()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_happy_path(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"stats": {"unexpected": 0}, "suites": []}),
        stderr="",
    )
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
    )
    names = [r.name for r in results]
    assert "smoke" in names
    smoke = next(r for r in results if r.name == "smoke")
    assert smoke.passed is True
    popen.return_value.terminate.assert_called_once()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=None)
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_dev_server_unhealthy(popen):
    popen.return_value = _devserver_proc(alive=True)
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
        health_timeout=1,
    )
    assert any(r.name == "dev_server_unhealthy" for r in results)
    popen.return_value.terminate.assert_called_once()


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_tests_failed_yields_per_test_results(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.return_value = MagicMock(
        returncode=1,
        stdout=json.dumps({
            "stats": {"unexpected": 1},
            "suites": [{
                "specs": [{
                    "title": "assigns income",
                    "file": "specs/budget.spec.ts",
                    "tests": [{
                        "results": [{
                            "status": "failed",
                            "error": {"message": "locator timed out"},
                        }],
                    }],
                }],
            }],
        }),
        stderr="",
    )
    results = smoke_validate(
        "/tmp/out",
        target_app={
            "base_url": "http://localhost:5173",
            "start_command": "npm run dev",
            "start_cwd": "/tmp/app",
            "health_path": "/",
        },
        enabled=True,
    )
    test_failures = [r for r in results if r.name.startswith("test_failure:")]
    assert len(test_failures) == 1
    assert "assigns income" in test_failures[0].name
    assert "locator timed out" in test_failures[0].output


@patch("qa_framework_generator_ts.validators._http_probe", return_value=200)
@patch("qa_framework_generator_ts.validators.subprocess.run")
@patch("qa_framework_generator_ts.validators.subprocess.Popen")
def test_smoke_terminates_devserver_even_on_exception(popen, run, probe):
    popen.return_value = _devserver_proc(alive=True)
    run.side_effect = RuntimeError("playwright exploded")
    try:
        smoke_validate(
            "/tmp/out",
            target_app={
                "base_url": "http://localhost:5173",
                "start_command": "npm run dev",
                "start_cwd": "/tmp/app",
                "health_path": "/",
            },
            enabled=True,
        )
    except RuntimeError:
        pass
    popen.return_value.terminate.assert_called_once()
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_validators_smoke.py -v`
Expected: FAIL — `smoke_validate` doesn't exist.

- [ ] **Step 3: Extend validators.py**

Append to `qa_framework_generator_ts/validators.py`:
```python
import json
import shlex
import time
import urllib.error
import urllib.request


def _http_probe(url: str, timeout: float = 1.0) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except (urllib.error.URLError, OSError, ConnectionError):
        return None


def _wait_for_health(
    base_url: str,
    health_path: str,
    timeout: int,
    proc: subprocess.Popen,
) -> bool:
    deadline = time.monotonic() + timeout
    url = base_url.rstrip("/") + health_path
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False  # dev server died
        if _http_probe(url) is not None:
            return True
        time.sleep(0.5)
    return False


def _terminate(proc: subprocess.Popen, grace: float = 5.0) -> None:
    try:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)
    except ProcessLookupError:
        pass


def _parse_failures(report_json: str) -> list[ValidationResult]:
    failures: list[ValidationResult] = []
    try:
        report = json.loads(report_json)
    except json.JSONDecodeError:
        return [ValidationResult(
            name="smoke_unparseable_report",
            passed=False,
            output=_trim_output(report_json),
            fix_hint="playwright json report was malformed",
        )]
    for suite in report.get("suites", []) or []:
        for spec in suite.get("specs", []) or []:
            title = spec.get("title", "unknown")
            file = spec.get("file", "unknown")
            for t in spec.get("tests", []) or []:
                for r in t.get("results", []) or []:
                    if r.get("status") == "failed":
                        msg = (r.get("error") or {}).get("message", "")
                        failures.append(ValidationResult(
                            name=f"test_failure:{title}",
                            passed=False,
                            output=f"file={file}\n{_trim_output(msg)}",
                            fix_hint="fix locator/assertion to match the rendered UI",
                        ))
    return failures


def smoke_validate(
    output_dir: str,
    target_app: dict,
    enabled: bool,
    health_timeout: int = 30,
) -> list[ValidationResult]:
    if not enabled:
        return [ValidationResult(name="smoke", passed=True, output="disabled (no --smoke flag)")]

    base_url = target_app["base_url"]
    cmd = shlex.split(target_app["start_command"])
    cwd = target_app["start_cwd"]
    health_path = target_app["health_path"]

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        if not _wait_for_health(base_url, health_path, health_timeout, proc):
            return [ValidationResult(
                name="dev_server_unhealthy",
                passed=False,
                output=f"dev server did not respond at {base_url}{health_path} within {health_timeout}s",
                fix_hint="check start_command, start_cwd, health_path in target_app",
            )]

        run_result = subprocess.run(
            ["npx", "playwright", "test", "--reporter=json"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=600,
            env={"BASE_URL": base_url, **__import__("os").environ},
        )

        if run_result.returncode == 0:
            return [ValidationResult(name="smoke", passed=True, output="all tests passed")]

        failures = _parse_failures(run_result.stdout)
        if not failures:
            return [ValidationResult(
                name="smoke_crashed",
                passed=False,
                output=_trim_output(run_result.stderr or run_result.stdout),
                fix_hint="playwright exited non-zero with no parseable failures",
            )]
        return failures
    finally:
        _terminate(proc)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_validators_smoke.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/validators.py tests/unit/test_validators_smoke.py
git commit -m "feat(validators): smoke step — health-probe + playwright run + cleanup

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: LLM Wrapper

**Files:**
- Create: `qa_framework_generator_ts/llm.py`
- Create: `tests/unit/test_llm.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_llm.py`:
```python
import os
from unittest.mock import patch

import pytest

from qa_framework_generator_ts.llm import (
    MissingAPIKeyError,
    get_openai_chat_model,
)


def test_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError) as exc:
        get_openai_chat_model()
    assert ".env.example" in str(exc.value)


def test_returns_model_when_key_present(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    model = get_openai_chat_model()
    assert model is not None
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_llm.py -v`

- [ ] **Step 3: Implement llm.py**

`qa_framework_generator_ts/llm.py`:
```python
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


class MissingAPIKeyError(RuntimeError):
    """Raised when OPENAI_API_KEY is absent. See .env.example."""


def get_openai_chat_model():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise MissingAPIKeyError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1")
    return ChatOpenAI(model=model_name, api_key=api_key, temperature=0)
```

Add to `pyproject.toml` dependencies: `"langchain-openai>=0.3.0",` and reinstall: `uv pip install -e ".[dev]"`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_llm.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/llm.py tests/unit/test_llm.py pyproject.toml
git commit -m "feat(llm): OpenAI chat model factory with MissingAPIKeyError

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Structured Output Pydantic Models

**Files:**
- Create: `qa_framework_generator_ts/models.py`
- Create: `tests/unit/test_models.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_models.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_models.py -v`

- [ ] **Step 3: Implement models.py**

`qa_framework_generator_ts/models.py`:
```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_models.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/models.py tests/unit/test_models.py
git commit -m "feat(models): structured-output Pydantic models for LLM nodes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: Prompt Builders

**Files:**
- Create: `qa_framework_generator_ts/prompts.py`
- Create: `tests/unit/test_prompts.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_prompts.py`:
```python
from qa_framework_generator_ts.prompts import (
    build_requirements_prompt,
    build_blueprint_prompt,
    build_page_object_prompt,
    build_test_case_prompt,
    build_review_prompt,
    build_repair_prompt,
    LOCATOR_HIERARCHY,
    FORBIDDEN_PATTERNS,
)


def test_locator_hierarchy_constant_lists_user_facing_first():
    # testid first per design (most resilient); then role+name; then label; etc.
    assert LOCATOR_HIERARCHY[0] == "testid"
    assert LOCATOR_HIERARCHY[1] == "role"
    assert "css" not in LOCATOR_HIERARCHY
    assert "xpath" not in LOCATOR_HIERARCHY


def test_forbidden_patterns_include_known_antipatterns():
    assert "page.waitForTimeout" in FORBIDDEN_PATTERNS
    assert "setTimeout" in FORBIDDEN_PATTERNS
    assert "page.locator(" in FORBIDDEN_PATTERNS  # CSS/XPath gateway


def test_requirements_prompt_mentions_playwright():
    p = build_requirements_prompt({"project_name": "x", "target_app": {"name": "X"}})
    assert "Playwright" in p
    assert "web-first" in p.lower()


def test_blueprint_prompt_includes_fixtures_requirement():
    p = build_blueprint_prompt({"goals": ["g"]}, {"pages": [], "flows": []})
    assert "fixture" in p.lower()


def test_page_object_prompt_states_locator_hierarchy_and_forbids_css():
    page = {
        "name": "HomePage",
        "url": "/",
        "elements": [{"name": "x", "locator": {"strategy": "testid", "value": "x"}}],
        "actions": [],
    }
    p = build_page_object_prompt(page, "demo")
    for s in LOCATOR_HIERARCHY:
        assert s in p
    assert "CSS" in p or "css" in p
    assert "XPath" in p or "xpath" in p


def test_test_case_prompt_demands_web_first_assertions():
    flow = {"name": "F", "tags": [], "steps": [], "assertions": []}
    p = build_test_case_prompt(flow, [], "demo")
    assert "test.step" in p
    assert "await expect" in p


def test_review_prompt_carries_files_and_findings():
    p = build_review_prompt(
        [{"path": "src/pages/HomePage.ts", "content": "class HomePage{}"}],
        [{"name": "tsc", "passed": True, "output": "ok"}],
    )
    assert "HomePage.ts" in p


def test_repair_prompt_quotes_failure_output():
    p = build_repair_prompt(
        file_path="src/pages/HomePage.ts",
        file_content="class HomePage {}",
        failures=[{"name": "tsc", "output": "TS2304", "fix_hint": "define x"}],
    )
    assert "TS2304" in p
    assert "HomePage.ts" in p
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_prompts.py -v`

- [ ] **Step 3: Implement prompts.py**

`qa_framework_generator_ts/prompts.py`:
```python
from __future__ import annotations

import json


LOCATOR_HIERARCHY = ["testid", "role", "label", "text", "placeholder", "altText", "title"]

FORBIDDEN_PATTERNS = [
    "page.waitForTimeout",
    "setTimeout",
    "page.locator(",  # disallow ad-hoc CSS/XPath
    "expect(await ",   # disallow non-web-first assertions
]


_LOCATOR_RULES = (
    "Locator hierarchy (use the highest tier that fits):\n"
    + "\n".join(f"  {i+1}. getBy{s[0].upper()}{s[1:]}(...)" for i, s in enumerate(LOCATOR_HIERARCHY))
    + "\nNEVER use page.locator() with CSS selectors or XPath. "
      "NEVER use page.waitForTimeout, setTimeout, or manual sleeps. "
      "ALWAYS use Playwright web-first assertions (await expect(locator).toX(...)). "
      "NEVER write expect(await locator.isVisible()).toBe(true)."
)


def build_requirements_prompt(config_data: dict) -> str:
    return (
        "You are writing the requirements for a Playwright + TypeScript end-to-end test framework.\n\n"
        f"App config (JSON):\n```json\n{json.dumps(config_data, indent=2)}\n```\n\n"
        "Produce: testing goals, coverage areas, and risk priorities. "
        "Keep in mind Playwright conventions: web-first assertions, fixtures, projects per browser, "
        "trace-on-first-retry, locator priorities (getByRole/getByLabel/getByTestId)."
    )


def build_blueprint_prompt(requirements: dict, config_data: dict) -> str:
    return (
        "Produce a blueprint for the framework: which page-object classes, which spec files, "
        "which fixtures the spec layer will consume, and which tags map onto Playwright's "
        "test.describe.configure({ tag }) usage.\n\n"
        f"Requirements:\n```json\n{json.dumps(requirements, indent=2)}\n```\n\n"
        f"Config:\n```json\n{json.dumps({k: v for k, v in config_data.items() if k in ('pages','flows')}, indent=2)}\n```"
    )


def build_page_object_prompt(page: dict, package_name: str) -> str:
    return (
        f"Generate a TypeScript Playwright page-object class for page '{page['name']}' "
        f"in package '{package_name}'.\n\n"
        f"YAML page spec:\n```json\n{json.dumps(page, indent=2)}\n```\n\n"
        f"{_LOCATOR_RULES}\n\n"
        "Output must satisfy:\n"
        "- class with constructor(private readonly page: Page)\n"
        "- one readonly Locator field per element\n"
        "- one async method per action with typed parameters\n"
        "- a goto() method using the spec's url"
    )


def build_test_case_prompt(flow: dict, pages: list[dict], package_name: str) -> str:
    return (
        f"Generate a TypeScript Playwright spec for flow '{flow['name']}'.\n\n"
        f"Flow spec:\n```json\n{json.dumps(flow, indent=2)}\n```\n\n"
        f"Available pages:\n```json\n{json.dumps([p['name'] for p in pages], indent=2)}\n```\n\n"
        "Output must:\n"
        "- import { test, expect } from '../src/fixtures'\n"
        "- wrap each step in `await test.step('label', async () => { ... })`\n"
        "- use `await expect(locator).toX(...)` for every assertion (web-first)\n"
        "- never use expect(await locator.isVisible()).toBe(true)\n"
        f"{_LOCATOR_RULES}"
    )


def build_review_prompt(files: list[dict], validation_results: list[dict]) -> str:
    files_summary = "\n".join(f"### {f['path']}\n```ts\n{f['content']}\n```" for f in files)
    val_summary = "\n".join(f"- {r['name']}: {'PASS' if r['passed'] else 'FAIL'} — {r['output'][:200]}" for r in validation_results)
    return (
        "You are reviewing a generated Playwright+TypeScript framework. "
        "Return passed=true only if every file follows the structural contract "
        "(getBy* locators only, web-first assertions, fixtures pattern, no waitForTimeout, "
        "no floating promises, no expect(await ...).toBe).\n\n"
        f"Validation summary:\n{val_summary}\n\n"
        f"Files:\n{files_summary}"
    )


def build_repair_prompt(file_path: str, file_content: str, failures: list[dict]) -> str:
    failures_block = "\n".join(
        f"- {f['name']}: {f.get('output','')[:1000]}\n  hint: {f.get('fix_hint','')}"
        for f in failures
    )
    return (
        f"Repair the following file. Return ONLY the new file contents — no markdown, no explanation.\n\n"
        f"File path: {file_path}\n\n"
        f"Current contents:\n```ts\n{file_content}\n```\n\n"
        f"Failures to address:\n{failures_block}\n\n"
        f"Constraints:\n{_LOCATOR_RULES}"
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_prompts.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/prompts.py tests/unit/test_prompts.py
git commit -m "feat(prompts): TS/Playwright prompt builders with locator hierarchy

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: Evaluator (DeepEval With TS Criteria)

**Files:**
- Create: `qa_framework_generator_ts/evaluator.py`
- Create: `tests/unit/test_evaluator.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_evaluator.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_evaluator.py -v`

- [ ] **Step 3: Implement evaluator.py**

`qa_framework_generator_ts/evaluator.py`:
```python
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
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_evaluator.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/evaluator.py tests/unit/test_evaluator.py
git commit -m "feat(evaluator): DeepEval GEval with TS-specific criteria

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 13: Repair Module

**Files:**
- Create: `qa_framework_generator_ts/repair.py`
- Create: `tests/unit/test_repair.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_repair.py`:
```python
from unittest.mock import patch, MagicMock

from qa_framework_generator_ts.repair import repair_files, FILE_TOO_LARGE_BYTES
from qa_framework_generator_ts.state import GeneratedFile, ValidationResult


def _mock_llm_returning(content: str):
    llm = MagicMock()
    response = MagicMock()
    response.content = content
    llm.invoke = MagicMock(return_value=response)
    return llm


@patch("qa_framework_generator_ts.repair.get_openai_chat_model")
def test_repair_files_rewrites_only_targeted_files(get_llm):
    get_llm.return_value = _mock_llm_returning("class Fixed {}")
    files = [
        GeneratedFile(path="src/pages/HomePage.ts", content="class HomePage {}", kind="typescript"),
        GeneratedFile(path="src/pages/Other.ts", content="class Other {}", kind="typescript"),
    ]
    failures = [
        ValidationResult(
            name="test_failure:HomePage broken",
            passed=False,
            output="locator timed out\nfile=src/pages/HomePage.ts",
            fix_hint="fix locator",
        )
    ]
    result = repair_files(files, failures)
    home = next(f for f in result if f.path == "src/pages/HomePage.ts")
    other = next(f for f in result if f.path == "src/pages/Other.ts")
    assert home.content == "class Fixed {}"
    assert other.content == "class Other {}"


@patch("qa_framework_generator_ts.repair.get_openai_chat_model")
def test_repair_files_skips_files_over_size_cap(get_llm):
    big_content = "x" * (FILE_TOO_LARGE_BYTES + 1)
    files = [GeneratedFile(path="src/pages/Big.ts", content=big_content, kind="typescript")]
    failures = [
        ValidationResult(name="tsc", passed=False, output="error in src/pages/Big.ts", fix_hint="")
    ]
    result = repair_files(files, failures)
    assert result[0].content == big_content  # unchanged
    get_llm.assert_not_called()


def test_repair_detects_stuck_state():
    from qa_framework_generator_ts.repair import is_stuck
    f1 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    f2 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    f3 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    assert is_stuck([[f1], [f2], [f3]]) is True


def test_repair_not_stuck_when_output_changes():
    from qa_framework_generator_ts.repair import is_stuck
    f1 = ValidationResult(name="tsc", passed=False, output="error A")
    f2 = ValidationResult(name="tsc", passed=False, output="error B")
    f3 = ValidationResult(name="tsc", passed=False, output="error A")
    assert is_stuck([[f1], [f2], [f3]]) is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_repair.py -v`

- [ ] **Step 3: Implement repair.py**

`qa_framework_generator_ts/repair.py`:
```python
from __future__ import annotations

import re

from qa_framework_generator_ts.llm import get_openai_chat_model
from qa_framework_generator_ts.prompts import build_repair_prompt
from qa_framework_generator_ts.state import GeneratedFile, ValidationResult


FILE_TOO_LARGE_BYTES = 50 * 1024


def _failures_by_file(
    failures: list[ValidationResult],
    files: list[GeneratedFile],
) -> dict[str, list[ValidationResult]]:
    mapping: dict[str, list[ValidationResult]] = {f.path: [] for f in files}
    file_paths = list(mapping.keys())
    for failure in failures:
        text = f"{failure.name}\n{failure.output}"
        for path in file_paths:
            if path in text:
                mapping[path].append(failure)
    return mapping


def repair_files(
    files: list[GeneratedFile],
    failures: list[ValidationResult],
) -> list[GeneratedFile]:
    by_file = _failures_by_file(failures, files)
    if not any(by_file.values()):
        # No file-scoped failures; nothing to repair locally.
        return list(files)

    llm = None
    new_files: list[GeneratedFile] = []
    for f in files:
        targeted = by_file.get(f.path, [])
        if not targeted:
            new_files.append(f)
            continue
        if len(f.content.encode("utf-8")) > FILE_TOO_LARGE_BYTES:
            new_files.append(f)  # caller should regenerate from scratch
            continue
        if llm is None:
            llm = get_openai_chat_model()
        prompt = build_repair_prompt(
            file_path=f.path,
            file_content=f.content,
            failures=[t.model_dump() for t in targeted],
        )
        response = llm.invoke(prompt)
        new_content = response.content if hasattr(response, "content") else str(response)
        new_content = _strip_code_fence(new_content)
        new_files.append(GeneratedFile(path=f.path, content=new_content, kind=f.kind))
    return new_files


def _strip_code_fence(text: str) -> str:
    m = re.match(r"^```[\w]*\n(.*?)\n```\s*$", text.strip(), re.DOTALL)
    return m.group(1) if m else text


def is_stuck(history: list[list[ValidationResult]]) -> bool:
    """True if last three rounds have identical failure signatures (same name+output)."""
    if len(history) < 3:
        return False
    last_three = history[-3:]
    sig = lambda rs: tuple(sorted((r.name, r.output) for r in rs if not r.passed))
    a, b, c = (sig(rs) for rs in last_three)
    return a == b == c and len(a) > 0
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_repair.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/repair.py tests/unit/test_repair.py
git commit -m "feat(repair): per-file repair with size cap and stuck detection

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 14: LangGraph Nodes & Routing

**Files:**
- Create: `qa_framework_generator_ts/graph.py`
- Create: `tests/unit/test_graph_routes.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_graph_routes.py`:
```python
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
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_graph_routes.py -v`

- [ ] **Step 3: Implement graph.py**

`qa_framework_generator_ts/graph.py`:
```python
from __future__ import annotations

from langgraph.graph import StateGraph, END

from qa_framework_generator_ts.state import GeneratedFile, GeneratorState, ValidationResult


# --- Deterministic nodes -----------------------------------------------------

def load_config_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.config import load_config
    cfg = load_config(state.config_path)
    return {
        "config_data": cfg.model_dump(),
        "project_name": cfg.project_name,
        "target_package": cfg.package_name,
        "output_dir": state.output_dir or cfg.output_dir,
    }


def render_static_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.config import FrameworkConfig
    from qa_framework_generator_ts.renderer import render_static_templates
    cfg = FrameworkConfig(**state.config_data)
    files = render_static_templates(cfg)
    return {"generated_files": files}


def write_files_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.file_writer import write_files
    write_files(state.generated_files, state.output_dir or "./out", force=True)
    return {"status": "generated"}


def static_validate_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.validators import validate_static
    results = validate_static(state.output_dir or "./out")
    return {"validation_results": results, "status": "validating"}


def smoke_validate_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.validators import smoke_validate
    target_app = state.config_data.get("target_app", {})
    results = smoke_validate(state.output_dir or "./out", target_app, enabled=state.smoke_enabled)
    return {"validation_results": list(state.validation_results) + results}


def final_report_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.file_writer import write_files
    failures = [r for r in state.validation_results if not r.passed]
    status = "failed" if failures else "done"
    report = _build_report(state)
    file = GeneratedFile(path="GENERATION_REPORT.md", content=report, kind="markdown")
    write_files([file], state.output_dir or "./out", force=True, cleanup=False)
    return {"status": status}


def _build_report(state: GeneratorState) -> str:
    passed = [r for r in state.validation_results if r.passed]
    failed = [r for r in state.validation_results if not r.passed]
    lines = [
        f"# Generation Report — {state.project_name}",
        "",
        f"**Status:** {state.status}",
        f"**Output:** {state.output_dir}",
        f"**Package:** {state.target_package}",
        f"**Repair attempts:** {state.repair_attempts}",
        f"**Smoke step:** {'enabled' if state.smoke_enabled else 'disabled'}",
        "",
        "## Files",
        "",
    ]
    for f in state.generated_files:
        lines.append(f"- `{f.path}`")
    lines += ["", f"## Validation — {len(passed)} passed / {len(failed)} failed", ""]
    for r in state.validation_results:
        icon = "✅" if r.passed else "❌"
        lines.append(f"- {icon} `{r.name}`")
        if not r.passed and r.output:
            first_line = r.output.split("\n", 1)[0][:200]
            lines.append(f"  - {first_line}")
    return "\n".join(lines) + "\n"


# --- LLM nodes ---------------------------------------------------------------

def requirements_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.llm import get_openai_chat_model
    from qa_framework_generator_ts.models import RequirementsOutput
    from qa_framework_generator_ts.prompts import build_requirements_prompt
    llm = get_openai_chat_model()
    structured = llm.with_structured_output(RequirementsOutput, method="function_calling")
    result: RequirementsOutput = structured.invoke(build_requirements_prompt(state.config_data))
    return {"requirements": result.model_dump()}


def blueprint_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.llm import get_openai_chat_model
    from qa_framework_generator_ts.models import BlueprintOutput
    from qa_framework_generator_ts.prompts import build_blueprint_prompt
    llm = get_openai_chat_model()
    structured = llm.with_structured_output(BlueprintOutput, method="function_calling")
    result: BlueprintOutput = structured.invoke(build_blueprint_prompt(state.requirements, state.config_data))
    return {"blueprint": result.model_dump()}


def generate_pages_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.config import FrameworkConfig
    from qa_framework_generator_ts.llm import get_openai_chat_model
    from qa_framework_generator_ts.models import PageObjectOutput, TestCaseOutput
    from qa_framework_generator_ts.prompts import build_page_object_prompt, build_test_case_prompt
    from qa_framework_generator_ts.renderer import render_page_object, render_fixtures, render_spec

    cfg = FrameworkConfig(**state.config_data)
    llm = get_openai_chat_model()
    pkg = cfg.package_name
    new_files: list[GeneratedFile] = []

    for page in cfg.pages:
        prompt = build_page_object_prompt(page.model_dump(), pkg)
        structured = llm.with_structured_output(PageObjectOutput, method="function_calling")
        out: PageObjectOutput = structured.invoke(prompt)
        content = render_page_object(
            class_name=out.class_name,
            url=out.url,
            elements=out.elements,
            actions=out.actions,
        )
        new_files.append(GeneratedFile(
            path=f"src/pages/{out.class_name}.ts",
            content=content,
            kind="typescript",
        ))

    fixtures_content = render_fixtures(pages=[{"name": p.name} for p in cfg.pages])
    new_files.append(GeneratedFile(path="src/fixtures.ts", content=fixtures_content, kind="typescript"))

    for flow in cfg.flows:
        prompt = build_test_case_prompt(flow.model_dump(), [p.model_dump() for p in cfg.pages], pkg)
        structured = llm.with_structured_output(TestCaseOutput, method="function_calling")
        out_t: TestCaseOutput = structured.invoke(prompt)
        spec_path = f"specs/{flow.name.lower()}.spec.ts"
        content = render_spec(
            describe=out_t.describe,
            test_name=out_t.test_name,
            tags=out_t.tags,
            used_fixtures=out_t.used_fixtures,
            steps=out_t.steps,
            assertions=out_t.assertions,
        )
        new_files.append(GeneratedFile(path=spec_path, content=content, kind="typescript"))

    return {"generated_files": list(state.generated_files) + new_files}


def evaluate_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.evaluator import evaluate_generated_files
    results = evaluate_generated_files(state.generated_files, state.config_data, state.eval_threshold)
    existing = [r for r in state.validation_results if not r.name.startswith("eval_")]
    return {"validation_results": existing + results}


def review_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.llm import get_openai_chat_model
    from qa_framework_generator_ts.models import ReviewOutput
    from qa_framework_generator_ts.prompts import build_review_prompt
    llm = get_openai_chat_model()
    structured = llm.with_structured_output(ReviewOutput, method="function_calling")
    prompt = build_review_prompt(
        [f.model_dump() for f in state.generated_files],
        [r.model_dump() for r in state.validation_results],
    )
    result: ReviewOutput = structured.invoke(prompt)
    if result.passed:
        return {"status": "done"}
    review_failure = ValidationResult(
        name="review",
        passed=False,
        output="; ".join(result.findings),
        fix_hint="address review findings",
    )
    return {"validation_results": list(state.validation_results) + [review_failure]}


def repair_node(state: GeneratorState) -> dict:
    from qa_framework_generator_ts.repair import repair_files
    from qa_framework_generator_ts.file_writer import write_files
    failures = [r for r in state.validation_results if not r.passed]
    fixed = repair_files(state.generated_files, failures)
    write_files(fixed, state.output_dir or "./out", force=True)
    return {
        "generated_files": fixed,
        "repair_attempts": state.repair_attempts + 1,
        "status": "repairing",
        "validation_results": [],
    }


# --- Routing -----------------------------------------------------------------

def route_after_evaluation(state: GeneratorState) -> str:
    eval_results = [r for r in state.validation_results if r.name.startswith("eval_")]
    return "write_files" if all(r.passed for r in eval_results) else "repair"


def route_after_static_validation(state: GeneratorState) -> str:
    return "smoke_validate" if all(r.passed for r in state.validation_results) else "repair"


def route_after_smoke_validation(state: GeneratorState) -> str:
    return "review" if all(r.passed for r in state.validation_results) else "repair"


def route_after_review(state: GeneratorState) -> str:
    return "final_report" if state.status == "done" else "repair"


def route_after_repair(state: GeneratorState) -> str:
    if state.repair_attempts >= state.max_repair_attempts:
        return "final_report"
    return "static_validate"


# --- Graph builder -----------------------------------------------------------

def build_graph():
    builder = StateGraph(GeneratorState)
    for name, fn in [
        ("load_config", load_config_node),
        ("requirements", requirements_node),
        ("blueprint", blueprint_node),
        ("render_static", render_static_node),
        ("generate_pages", generate_pages_node),
        ("evaluate", evaluate_node),
        ("write_files", write_files_node),
        ("static_validate", static_validate_node),
        ("smoke_validate", smoke_validate_node),
        ("review", review_node),
        ("repair", repair_node),
        ("final_report", final_report_node),
    ]:
        builder.add_node(name, fn)

    builder.set_entry_point("load_config")
    builder.add_edge("load_config", "requirements")
    builder.add_edge("requirements", "blueprint")
    builder.add_edge("blueprint", "render_static")
    builder.add_edge("render_static", "generate_pages")
    builder.add_edge("generate_pages", "evaluate")
    builder.add_edge("write_files", "static_validate")
    builder.add_conditional_edges("evaluate", route_after_evaluation,
                                  {"write_files": "write_files", "repair": "repair"})
    builder.add_conditional_edges("static_validate", route_after_static_validation,
                                  {"smoke_validate": "smoke_validate", "repair": "repair"})
    builder.add_conditional_edges("smoke_validate", route_after_smoke_validation,
                                  {"review": "review", "repair": "repair"})
    builder.add_conditional_edges("review", route_after_review,
                                  {"final_report": "final_report", "repair": "repair"})
    builder.add_conditional_edges("repair", route_after_repair,
                                  {"static_validate": "static_validate", "final_report": "final_report"})
    builder.add_edge("final_report", END)
    return builder.compile()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_graph_routes.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/graph.py tests/unit/test_graph_routes.py
git commit -m "feat(graph): 12-node LangGraph with routing functions

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 15: CLI Entry Point

**Files:**
- Create: `qa_framework_generator_ts/cli.py`
- Create: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli.py`:
```python
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from qa_framework_generator_ts.cli import main


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_invokes_graph_with_config_path(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "done"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml"])
    assert result.exit_code == 0
    g.invoke.assert_called_once()
    sent_state = g.invoke.call_args.args[0]
    assert sent_state["config_path"] == "examples/minimal.yaml"
    assert sent_state["smoke_enabled"] is False


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_smoke_flag_enables_smoke(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "done"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml", "--smoke"])
    assert result.exit_code == 0
    sent_state = g.invoke.call_args.args[0]
    assert sent_state["smoke_enabled"] is True


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_nonzero_exit_on_failed_status(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "failed"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml"])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/unit/test_cli.py -v`

- [ ] **Step 3: Implement cli.py**

`qa_framework_generator_ts/cli.py`:
```python
from __future__ import annotations

import sys

import click
from dotenv import load_dotenv


@click.command()
@click.option("--config", required=True, help="Path to YAML config.")
@click.option("--output-dir", default=None, help="Override output_dir from YAML.")
@click.option("--smoke", is_flag=True, default=False, help="Run live smoke step against target app.")
@click.option("--no-cleanup", is_flag=True, default=False, help="Skip cleanup of stale files.")
def main(config: str, output_dir: str | None, smoke: bool, no_cleanup: bool):
    """Generate a Playwright/TypeScript test framework from a YAML spec."""
    load_dotenv()
    from qa_framework_generator_ts.graph import build_graph

    initial = {
        "config_path": config,
        "output_dir": output_dir,
        "smoke_enabled": smoke,
    }
    graph = build_graph()
    final_state = graph.invoke(initial)
    status = final_state.get("status") if isinstance(final_state, dict) else final_state.status
    click.echo(f"Done. status={status}")
    if status not in ("done",):
        sys.exit(1)
```

- [ ] **Step 4: Add `click` and `python-dotenv` confirm in pyproject (already added in Task 1) and run tests**

Run: `uv run pytest tests/unit/test_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add qa_framework_generator_ts/cli.py tests/unit/test_cli.py
git commit -m "feat(cli): click entry point with --smoke and --no-cleanup flags

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 16: Minimal YAML Example

**Files:**
- Create: `examples/minimal.yaml`

- [ ] **Step 1: Write minimal.yaml**

`examples/minimal.yaml`:
```yaml
project_name: minimal-demo
package_name: minimal-demo
output_dir: ./minimal-output
target_app:
  name: MinimalApp
  base_url: http://localhost:5173
  start_command: npm run dev
  start_cwd: ../minimal-app
  health_path: /
browsers:
  - chromium
pages:
  - name: HomePage
    url: /
    elements:
      - name: heading
        locator: { strategy: role, role: heading, name: "Welcome" }
    actions: []
flows:
  - name: HomeFlow
    tags: [smoke]
    steps:
      - { page: HomePage, action: goto }
    assertions:
      - { on: HomePage.heading, expect: toBeVisible }
```

- [ ] **Step 2: Verify it loads**

Run: `uv run python -c "from qa_framework_generator_ts.config import load_config; print(load_config('examples/minimal.yaml').project_name)"`
Expected: `minimal-demo`

- [ ] **Step 3: Commit**

```bash
git add examples/minimal.yaml
git commit -m "docs(examples): minimal yaml — one page, one flow

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 17: BudgetZero YAML Example

**Files:**
- Create: `examples/budgetzero.yaml`

- [ ] **Step 1: Write budgetzero.yaml**

Pages reflect the 7 routes in `~/Desktop/llm-ai-projects/budgetzero-web/src/App.tsx`. Elements use the 9 known `data-testid` values plus role-based fallbacks.

`examples/budgetzero.yaml`:
```yaml
project_name: budgetzero-e2e
package_name: budgetzero
output_dir: ./budgetzero-output
target_app:
  name: BudgetZero
  base_url: http://localhost:5173
  start_command: npm run dev
  start_cwd: ../budgetzero-web
  health_path: /
browsers:
  - chromium
  - firefox
  - webkit
  - mobile-chrome
pages:
  - name: BudgetPage
    url: /
    elements:
      - name: categoryRowGroceries
        locator: { strategy: testid, value: category-row-groceries }
      - name: heading
        locator: { strategy: role, role: heading, name: "Budget" }
    actions: []

  - name: TransactionsPage
    url: /transactions
    elements:
      - name: transactionRow
        locator: { strategy: testid, value: transaction-row-tx1 }
      - name: addButton
        locator: { strategy: role, role: button, name: "Add" }
    actions: []

  - name: ReportsPage
    url: /reports
    elements:
      - name: reportIncome
        locator: { strategy: testid, value: report-income }
      - name: reportSpent
        locator: { strategy: testid, value: report-spent }
      - name: reportNet
        locator: { strategy: testid, value: report-net }
    actions: []

  - name: PlanPage
    url: /plan
    elements:
      - name: planRow
        locator: { strategy: testid, value: plan-row-groceries }
      - name: planTarget
        locator: { strategy: testid, value: plan-target-groceries }
    actions: []

  - name: GuidePage
    url: /guide
    elements:
      - name: guideStep1
        locator: { strategy: testid, value: guide-step-1 }
    actions: []

  - name: AccountsPage
    url: /accounts
    elements:
      - name: heading
        locator: { strategy: role, role: heading, name: "Accounts" }
    actions: []

  - name: DesignSystemPage
    url: /design-system
    elements:
      - name: heading
        locator: { strategy: role, role: heading, name: "Design System" }
    actions: []

flows:
  - name: BudgetSmoke
    tags: [smoke, budget]
    steps:
      - { page: BudgetPage, action: goto }
    assertions:
      - { on: BudgetPage.heading, expect: toBeVisible }

  - name: ReportsSmoke
    tags: [smoke, reports]
    steps:
      - { page: ReportsPage, action: goto }
    assertions:
      - { on: ReportsPage.reportIncome, expect: toBeVisible }
      - { on: ReportsPage.reportNet, expect: toBeVisible }

  - name: TransactionsSmoke
    tags: [smoke, transactions]
    steps:
      - { page: TransactionsPage, action: goto }
    assertions:
      - { on: TransactionsPage.addButton, expect: toBeVisible }
```

- [ ] **Step 2: Verify it loads**

Run: `uv run python -c "from qa_framework_generator_ts.config import load_config; print(len(load_config('examples/budgetzero.yaml').pages))"`
Expected: `7`

- [ ] **Step 3: Commit**

```bash
git add examples/budgetzero.yaml
git commit -m "docs(examples): budgetzero yaml — 7 pages + 3 smoke flows

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 18: Tiny-Vite-App Fixture For Hermetic Smoke Tests

**Files:**
- Create: `tests/fixtures/tiny-vite-app/package.json`
- Create: `tests/fixtures/tiny-vite-app/index.html`
- Create: `tests/fixtures/tiny-vite-app/vite.config.ts`
- Create: `tests/fixtures/tiny-vite-app/src/main.tsx`
- Create: `tests/fixtures/tiny-vite-app/src/App.tsx`
- Create: `tests/fixtures/tiny-vite-app/tsconfig.json`

- [ ] **Step 1: Write the fixture app**

`tests/fixtures/tiny-vite-app/package.json`:
```json
{
  "name": "tiny-vite-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": { "dev": "vite --port 5174" },
  "dependencies": { "react": "^18.3.0", "react-dom": "^18.3.0" },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

`tests/fixtures/tiny-vite-app/index.html`:
```html
<!DOCTYPE html>
<html>
  <head><title>Tiny</title></head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`tests/fixtures/tiny-vite-app/vite.config.ts`:
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()] });
```

`tests/fixtures/tiny-vite-app/src/main.tsx`:
```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
```

`tests/fixtures/tiny-vite-app/src/App.tsx`:
```tsx
export default function App() {
  return (
    <main>
      <h1 data-testid="hello">Hello from tiny app</h1>
      <button data-testid="btn">Click</button>
    </main>
  );
}
```

`tests/fixtures/tiny-vite-app/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 2: Verify the fixture is excluded from cleanup**

Already covered by `CLEANUP_IGNORE_PATTERNS` containing `node_modules`. Confirm by running the file_writer test suite again:

Run: `uv run pytest tests/unit/test_file_writer.py -v`
Expected: still PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/tiny-vite-app/
git commit -m "test(fixtures): tiny-vite-app for hermetic smoke tests

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 19: Integration Test — Full Generation With Mocked LLM

**Files:**
- Create: `tests/integration/test_e2e_generation_minimal.py`

- [ ] **Step 1: Write the integration test**

`tests/integration/test_e2e_generation_minimal.py`:
```python
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
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/integration/test_e2e_generation_minimal.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_e2e_generation_minimal.py
git commit -m "test(integration): e2e generation with mocked LLM — minimal yaml

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 20: Integration Test — Smoke Step Against Tiny App

**Files:**
- Create: `tests/integration/test_smoke_integration.py`

- [ ] **Step 1: Write the integration test**

`tests/integration/test_smoke_integration.py`:
```python
"""End-to-end smoke step against tests/fixtures/tiny-vite-app.

Runs real subprocesses. Marked `slow` so it can be skipped in fast CI.
Requires Node 20+ and a one-time `npm install` in the fixture dir.
"""
import shutil
import subprocess
from pathlib import Path

import pytest


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tiny-vite-app"


@pytest.fixture(scope="module")
def fixture_app_installed():
    if not shutil.which("npm"):
        pytest.skip("npm not in PATH")
    if not (FIXTURE / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=FIXTURE, check=True, timeout=300)
    yield FIXTURE


@pytest.mark.slow
def test_dev_server_unhealthy_is_caught(fixture_app_installed, tmp_path):
    from qa_framework_generator_ts.validators import smoke_validate
    # Point at a port nothing serves
    results = smoke_validate(
        str(tmp_path),
        target_app={
            "base_url": "http://localhost:1",
            "start_command": "node -e 'setTimeout(()=>{},10000)'",
            "start_cwd": str(fixture_app_installed),
            "health_path": "/",
        },
        enabled=True,
        health_timeout=2,
    )
    assert any(r.name == "dev_server_unhealthy" for r in results)


@pytest.mark.slow
def test_dev_server_starts_and_health_probe_succeeds(fixture_app_installed):
    from qa_framework_generator_ts.validators import _http_probe, _wait_for_health
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=fixture_app_installed,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ok = _wait_for_health("http://localhost:5174", "/", timeout=30, proc=proc)
        assert ok is True
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
```

Add to `pyproject.toml` under `[tool.pytest.ini_options]`:
```toml
markers = ["slow: real-subprocess integration tests"]
```

- [ ] **Step 2: Run the slow tests**

Run: `uv run pytest tests/integration/test_smoke_integration.py -v -m slow`
Expected: PASS (or SKIPPED if `npm` is missing).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_smoke_integration.py pyproject.toml
git commit -m "test(integration): smoke step against tiny-vite-app fixture

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 21: Project README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

`README.md`:
```md
# langgraph-playwright-ts-framework-generator

LangGraph-orchestrated generator that takes a YAML spec and emits a production-quality **Playwright + TypeScript** end-to-end test framework.

Sibling project to `langgraph-selenium-testng-framework-generator`. Same graph topology, different target stack.

## Quick start

```bash
# 1. Install
uv venv && uv pip install -e ".[dev]"

# 2. Provide an OpenAI key
cp .env.example .env && $EDITOR .env

# 3. Generate against the canonical demo (BudgetZero)
uv run qa-gen-ts --config examples/budgetzero.yaml

# 4. (optional) Run live smoke against the cloned BudgetZero
git clone https://github.com/ZeekrBaha/budgetzero-web ../budgetzero-web
(cd ../budgetzero-web && npm install)
uv run qa-gen-ts --config examples/budgetzero.yaml --smoke
```

## Graph

```
load_config → requirements → blueprint → render_static → generate_pages
→ evaluate → write_files → static_validate → smoke_validate → review
→ (final_report | repair → loop)
```

`smoke_validate` is a no-op pass unless `--smoke` is set.

## Locator policy

Generated page objects use the Playwright user-facing locators only:
`getByTestId`, `getByRole`, `getByLabel`, `getByText`, `getByPlaceholder`,
`getByAltText`, `getByTitle`. CSS and XPath are rejected by the YAML schema,
by the prompts, and by the DeepEval criteria.

## Tests

```bash
uv run pytest                       # fast unit + integration with mocked LLM
uv run pytest -m slow               # real-subprocess integration tests
RUN_LIVE_LLM=1 uv run pytest        # also runs tests that call OpenAI
```

## Design doc

`docs/superpowers/specs/2026-05-28-langgraph-playwright-ts-generator-design.md`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: project README with quick-start and locator policy

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 22: Final Verification

**Files:**
- None (verification only).

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest tests/unit -v`
Expected: all green. ~35 tests across config, state, file_writer, renderer (static + dynamic), validators (static + smoke), llm, models, prompts, evaluator, repair, graph routes, cli.

- [ ] **Step 2: Run the fast integration suite**

Run: `uv run pytest tests/integration -v -m "not slow"`
Expected: `test_e2e_generation_minimal` passes.

- [ ] **Step 3: Run the slow integration suite (optional, requires npm)**

Run: `uv run pytest tests/integration -v -m slow`
Expected: PASS or SKIPPED.

- [ ] **Step 4: Smoke-run the CLI against the minimal example**

Run: `uv run qa-gen-ts --config examples/minimal.yaml --output-dir /tmp/qa-gen-ts-smoke`

Expected:
- Exits with code 0 (status `done`) OR a meaningful failure visible in `/tmp/qa-gen-ts-smoke/GENERATION_REPORT.md` if the live OpenAI call surfaces eval failures.
- `/tmp/qa-gen-ts-smoke/` contains `package.json`, `tsconfig.json`, `playwright.config.ts`, `eslint.config.js`, `src/pages/HomePage.ts`, `src/fixtures.ts`, `specs/homeflow.spec.ts`, `README.md`, `GENERATION_REPORT.md`.

- [ ] **Step 5: Spot-check generated output for contract compliance**

```bash
grep -r "waitForTimeout" /tmp/qa-gen-ts-smoke/ && echo "FAIL" || echo "ok"
grep -r "page.locator(" /tmp/qa-gen-ts-smoke/ && echo "FAIL" || echo "ok"
grep -r "expect(await " /tmp/qa-gen-ts-smoke/ && echo "FAIL" || echo "ok"
```

Expected: three `ok` lines.

- [ ] **Step 6: Optional — run live BudgetZero smoke**

Pre-req: `git clone https://github.com/ZeekrBaha/budgetzero-web ../budgetzero-web && (cd ../budgetzero-web && npm install)`.

Run: `uv run qa-gen-ts --config examples/budgetzero.yaml --output-dir /tmp/qa-gen-ts-bz --smoke`

Expected: framework is generated; smoke step starts BudgetZero, runs the generated suite, terminates cleanly, and the report includes per-test results.

- [ ] **Step 7: Final commit if anything was tweaked during verification**

```bash
git add -A
git commit -m "chore: post-verification fixes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>" || echo "nothing to commit"
```

---

## Plan Self-Review Checklist (for the executor — review BEFORE starting Task 1)

- [ ] Confirm `~/Desktop/llm-ai-projects/langgraph-playwright-ts-framework-generator/` exists with the design doc committed.
- [ ] Confirm `~/Desktop/llm-ai-projects/budgetzero-web/` exists (Task 17 references its `src/App.tsx` and `data-testid` attributes — already verified during brainstorming).
- [ ] Confirm `uv`, `python ≥ 3.12`, and `git` are installed.
- [ ] Skim the design doc once: `docs/superpowers/specs/2026-05-28-langgraph-playwright-ts-generator-design.md`. Every section in the design maps to one or more tasks above.
