# LangGraph Playwright/TypeScript Framework Generator — Design

**Date:** 2026-05-28
**Status:** Approved by user, awaiting spec review
**Source generator (reference):** `~/Desktop/llm-ai-projects/langgraph-selenium-testng-framework-generator/`
**Canonical test target:** `~/Desktop/llm-ai-projects/budgetzero-web/` (React 19 + Vite + Convex)

---

## 1. Purpose

A LangGraph-orchestrated generator that takes a YAML spec describing a web app's routes, page elements, and user flows, and emits a production-quality **Playwright + TypeScript** end-to-end test framework. Same architectural skeleton as the existing Java/Selenium/TestNG generator; the payload at each node is rewritten for the TS/Playwright target.

The generator is generalizable. BudgetZero is the canonical demo (handwritten `examples/budgetzero.yaml`), not the only supported target.

### Non-goals

- Rewriting the Java generator. Both coexist as sibling repos.
- Scraping the target app's source. YAML is the source of truth.
- Windows support for the live smoke step (v1 is macOS/Linux only; static validation still works on Windows).

---

## 2. Architecture

### Repo layout (new sibling)

```
~/Desktop/llm-ai-projects/langgraph-playwright-ts-framework-generator/
  pyproject.toml
  uv.lock
  .env.example
  README.md
  qa_framework_generator_ts/
    __init__.py
    __main__.py
    cli.py
    config.py          # Pydantic schema for YAML input
    graph.py           # LangGraph nodes + wiring
    state.py           # Pydantic GeneratorState
    llm.py             # OpenAI structured-output wrapper
    models.py          # RequirementsOutput, BlueprintOutput, PageObjectOutput, TestCaseOutput, ReviewOutput
    prompts.py         # TS/Playwright-aware prompts
    renderer.py        # Jinja2 rendering of TS templates
    evaluator.py       # DeepEval GEval with TS criteria
    validators.py      # tsc + eslint + playwright list + smoke
    repair.py
    file_writer.py
    templates/
      ts/              # static framework files
      prompts/         # prompt templates
  examples/
    budgetzero.yaml    # canonical demo input
    minimal.yaml
  tests/
    unit/
    integration/
    fixtures/
      tiny-vite-app/   # 50-line app for hermetic smoke-step testing
  docs/
    superpowers/specs/
    prompt-contracts.md
    generated-framework-contract.md
```

The Python package is `qa_framework_generator_ts` (parallel to the Java repo's `qa_framework_generator`) so both can coexist in one venv.

### LangGraph topology (unchanged from Java generator)

```
load_config → requirements → blueprint → render_static → generate_pages
→ evaluate → write_files → static_validate → smoke_validate → review
→ (final_report | repair → loop, capped at max_repair_attempts)
```

`smoke_validate` replaces `maven_validate`. When `--smoke` is not set, it is a no-op pass — the graph branches identically at runtime regardless.

---

## 3. Input Schema (YAML)

```yaml
project_name: budgetzero-e2e
package_name: budgetzero        # used as npm package name + import root (NOT a JVM package)
output_dir: ../playwright-ts-framework-output
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
      - name: readyToAssign
        locator: { strategy: testid, value: ready-to-assign }
      - name: assignButton
        locator: { strategy: role, role: button, name: Assign }
      - name: incomeInput
        locator: { strategy: label, value: Income }
    actions:
      - name: assignIncome
        params: [{ name: amount, type: number }]
        steps:
          - { do: fill, target: incomeInput, value: "{amount}" }
          - { do: click, target: assignButton }

flows:
  - name: AssignIncomeFlow
    tags: [smoke, budget]
    steps:
      - { page: BudgetPage, action: goto }
      - { page: BudgetPage, action: assignIncome, args: { amount: 500 } }
    assertions:
      - { on: BudgetPage.readyToAssign, expect: toHaveText, value: "$0" }
```

### Key constraints (enforced in `config.py`)

- **`locator.strategy`** is one of: `testid | role | label | text | placeholder | altText | title`. CSS and XPath are deliberately not accepted.
- **Pages, flows arrays** require `min_length=1`.
- **Cross-references validated**: flow `page` names must exist; assertion `on` references (`PageName.elementName`) must resolve.
- **Duplicate names rejected** for both pages and flows.
- **Reserved name collisions** (`page`, `goto`, `locator`, etc.) rejected with a clear error message that lists the reserved set.

---

## 4. Generated Framework Shape

```
<output_dir>/
  package.json                        # static
  tsconfig.json                       # strict, noUncheckedIndexedAccess
  playwright.config.ts                # static, projects[] from YAML
  eslint.config.js                    # @typescript-eslint/no-floating-promises on
  .gitignore
  .github/workflows/test.yml          # CI with shard matrix
  README.md                           # lists pages/flows + run instructions
  src/
    fixtures.ts                       # LLM-generated
    pages/
      BudgetPage.ts                   # LLM-generated, one per YAML page
      TransactionsPage.ts
    helpers/
      selectors.ts                    # static
      money.ts                        # static
  specs/
    budget.spec.ts                    # LLM-generated, one per YAML flow
  GENERATION_REPORT.md
```

### Static vs LLM-generated

Static (Jinja-rendered from `FrameworkConfig`): `package.json`, `tsconfig.json`, `playwright.config.ts`, `eslint.config.js`, `.gitignore`, CI workflow, `helpers/*.ts`, `README.md`, `GENERATION_REPORT.md`.

LLM-generated (with templates enforcing structure): `pages/*.ts`, `fixtures.ts`, `specs/*.ts`.

### Structural contract for LLM-generated files

**Page object (`pages/<Name>Page.ts`):**
- Class with `constructor(private page: Page)`.
- One `readonly` Locator field per YAML element, built via `getByRole`/`getByLabel`/`getByText`/`getByTestId`/`getByPlaceholder`/`getByAltText`/`getByTitle`. Never `page.locator()` with CSS/XPath.
- One async method per YAML action.
- A `goto()` method whose URL comes from the YAML.
- No `page.waitForTimeout`, no manual `waitFor`, no `setTimeout`.

**Fixture (`fixtures.ts`):**
- Single `export const test = base.extend<{...}>({...})` with one fixture per page class.
- Each fixture body: `async ({ page }, use) => { await use(new XPage(page)); }`.
- Re-exports `expect` so specs import only from `../src/fixtures`.

**Spec (`specs/<flow>.spec.ts`):**
- `import { test, expect } from '../src/fixtures';`
- `test.describe(flowName, ...)` with optional `tag` from YAML.
- Every step wrapped in `await test.step('descriptive name', async () => { ... })`.
- Every assertion is a web-first `await expect(locator).toX(...)`.
- No `expect(await locator.isVisible()).toBe(true)` anti-pattern.
- No floating promises. No `page.waitForTimeout`.

### `playwright.config.ts` defaults (locked, not LLM-tunable)

```ts
export default defineConfig({
  testDir: './specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [['github'], ['html']] : 'list',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [ /* from YAML browsers[] */ ],
});
```

These are Playwright's officially recommended defaults — not opinions.

### CI workflow

Matrix on `shard: [1, 2, 3, 4]` with `--shard=${{ matrix.shard }}/4`. Installs only the browsers used. Uploads `playwright-report/` and `test-results/` as artifacts.

---

## 5. LangGraph Nodes & Data Flow

### Deterministic nodes

| Node | Reads | Writes | Notes |
|---|---|---|---|
| `load_config` | `state.config_path` | `config_data`, `project_name`, `target_package`, `output_dir` | Unchanged from Java generator (Pydantic schema is TS-aware). |
| `render_static` | `config_data` | `generated_files` ← rendered static templates | Renders `package.json`, `tsconfig.json`, `playwright.config.ts`, `eslint.config.js`, CI workflow, helpers, README. |
| `write_files` | `generated_files`, `output_dir` | filesystem | Atomic write + cleanup of non-listed files (preserves `node_modules/`, `playwright-report/`, `test-results/`, `.git/`). |
| `static_validate` | `generated_files`, `output_dir` | `validation_results` | Runs `tsc --noEmit -p tsconfig.json`, `eslint .`, `playwright test --list` in sequence. Short-circuits on first failure. |
| `smoke_validate` | `target_app`, `output_dir` | `validation_results`, `smoke_log` | No-op when `--smoke` not set. Otherwise: starts `start_command` in `start_cwd`, polls `health_path` (30s timeout), runs `npx playwright test --reporter=json`, parses results, always cleans up the dev-server process. |
| `final_report` | full state | `GENERATION_REPORT.md` | Includes smoke section when applicable. |

### LLM nodes

| Node | Prompt | Structured output | TS-specific contract |
|---|---|---|---|
| `requirements` | `build_requirements_prompt(config_data)` | `RequirementsOutput` | Prompt mentions Playwright web-first assertions and locator hierarchy. |
| `blueprint` | `build_blueprint_prompt(requirements, config_data)` | `BlueprintOutput` (page_classes, spec_files, fixtures, tags) | New `fixtures` field. |
| `generate_pages` | One call per page + one per flow | `PageObjectOutput`, `TestCaseOutput` | Prompts enforce locator hierarchy: `testid > role+name > label > text > placeholder > altText > title`. CSS/XPath forbidden. |
| `evaluate` | DeepEval `GEval` per page + per spec | `ValidationResult[]` | Reuses `evaluator.py` module pattern from Java generator with TS-specific criteria strings. |
| `review` | `build_review_prompt(generated_files, validation_results)` | `ReviewOutput { passed, findings }` | Final LLM-as-judge pass. |
| `repair` | `build_repair_prompt(file, failures)` | repaired file content | Same loop, same `max_repair_attempts` cap (default 3). |

### DeepEval criteria (replaces Java's Selenium criteria)

```python
_PAGE_OBJECT_CRITERIA_TS = (
  "The TypeScript Playwright page object class must satisfy ALL of:\n"
  "1. Class name exactly matches the page name from the spec.\n"
  "2. Constructor accepts `page: Page` as a private field.\n"
  "3. Every YAML element appears as a readonly Locator field.\n"
  "4. Locators are built from getByRole, getByLabel, getByText, getByTestId, "
  "getByPlaceholder, getByAltText, or getByTitle — never page.locator() with CSS or XPath.\n"
  "5. Every YAML action exists as an async method with matching parameters.\n"
  "6. No page.waitForTimeout, no setTimeout, no manual sleeps.\n"
  "7. Methods use locator actions directly; no `await locator.waitFor()` before clicks.\n"
)

_SPEC_CRITERIA_TS = (
  "The TypeScript Playwright spec file must satisfy ALL of:\n"
  "1. Imports `test` and `expect` from the project's fixtures module, not from @playwright/test.\n"
  "2. Every YAML step appears, wrapped in `await test.step('...', async () => { ... })`.\n"
  "3. Every YAML assertion is a web-first `await expect(locator).toX(...)` call.\n"
  "4. No expect(await locator.isVisible()).toBe(true) anti-pattern.\n"
  "5. No floating promises (every async call awaited).\n"
  "6. No page.waitForTimeout.\n"
  "7. Test tags from YAML appear via test.describe.configure({ tag }).\n"
)
```

### Routing functions

Unchanged in shape from Java generator:
- `route_after_evaluation`: eval results pass → `write_files`; else `repair`.
- `route_after_static_validation`: pass → `smoke_validate`; else `repair`.
- `route_after_smoke_validation` (renamed): pass → `review`; else `repair`.
- `route_after_review`: `done` → `final_report`; else `repair`.
- `route_after_repair`: under attempt cap → `static_validate`; else `final_report`.

### State additions

`GeneratorState` adds two fields beyond the Java generator:
- `smoke_enabled: bool = False`
- `smoke_log: str | None = None`

---

## 6. Error Handling

### LLM failures

Each LLM node catches `openai` exceptions and `pydantic.ValidationError`, retries with exponential backoff (1s → 2s → 4s, max 3 attempts), then writes `ValidationResult(passed=False, name='llm_<node>', ...)` and lets the existing repair loop handle it.

### Static-validator subprocess failures

`subprocess.run(..., capture_output=True, text=True, timeout=120)`. Non-zero exit → `ValidationResult` with stderr trimmed head-and-tail style (1.5 KB from start + 1.5 KB from end, joined by `…[truncated]…`). Timeout → fail-fast with a `*_timeout` named result; the repair loop won't fix timeouts.

### Smoke-step failures

Three distinct paths:

1. **Dev server won't start** (process exits during health-poll, or 30s timeout): one `ValidationResult` named `dev_server_unhealthy` with captured stdout/stderr, `state.status = 'smoke_unavailable'`, **skip repair** for this round.
2. **Test run produced JSON but tests failed**: each failed test becomes a `ValidationResult` with title, file path, and trimmed error. These enter the repair loop — the most useful failures.
3. **Playwright crashed mid-run**: one `ValidationResult` named `smoke_crashed` with stderr; skip repair.

### Process cleanup

`smoke_validate` uses `try/finally` that always `process.terminate()` the dev server with a 5s grace period before `kill()`. Integration tests verify no orphan `node` processes after SIGINT-ing the generator mid-run.

### Repair-loop runaway guard

If the same `ValidationResult.name` fails on three consecutive attempts with identical `output`, the loop short-circuits to `final_report` with status `stuck`. Cheap improvement the Java generator lacks.

### Config validation

Pydantic catches schema errors before any LLM call. Tested invariants:
- CSS or XPath locator → `ValidationError`.
- Flow referencing undefined page → `ValidationError`.
- Flow assertion referencing undefined element → `ValidationError`.
- Duplicate page or flow names → `ValidationError`.
- Reserved-name collisions → `ValidationError`.

### Other edge cases

- **Generator with no `OPENAI_API_KEY`**: `llm.py` raises a typed `MissingAPIKeyError` at first LLM call, pointing at `.env.example`.
- **Output dir contains unrelated files**: `cleanup=True` removes them; `--no-cleanup` flag plus a confirmation prompt if more than 20 files would be deleted.
- **Browsers in YAML not installed**: CI workflow installs the union; local README documents `npx playwright install --with-deps` as a setup step.
- **File too large to repair** (>50 KB): repair path skipped, regeneration re-invokes `generate_pages` for that file only.
- **Windows + `--smoke`**: warning emitted, smoke step skipped, static validation still runs.

---

## 7. Testing Strategy

Mirrors the Java generator's `tests/unit/` + `tests/integration/` layout.

### Unit tests

| File | Covers |
|---|---|
| `test_config.py` | YAML loading + Pydantic invariants (all five rejection cases above + happy path). |
| `test_renderer.py` | Jinja templates produce strings matching golden snapshots for page object, fixtures, spec. Regenerated with `pytest --snapshot-update`. |
| `test_prompt_outputs.py` | Given a fixed YAML page spec, the prompt text contains locator hierarchy + disallowed-patterns list. No LLM call. |
| `test_validators.py` | Mocked subprocess; verifies short-circuit on first failure + `ValidationResult` assembly. |
| `test_graph_routes.py` | Pure routing-function tests with crafted `GeneratorState`. Port verbatim from Java repo. |
| `test_repair.py` | Repair prompt assembly with mocked LLM; failure context included. |
| `test_evaluator.py` | DeepEval mocked; TS criteria strings passed correctly. |
| `test_smoke_validate.py` | Mocked `subprocess.Popen`; health-poll loop, three JSON parsing shapes (pass/fail/crash), cleanup on every path. |

### Integration tests

| File | Covers |
|---|---|
| `test_e2e_generation_minimal.py` | Full graph against `examples/minimal.yaml` with LLM mocked to return canned outputs. Asserts files exist, `tsc --noEmit` passes against generated output, structure matches contract. **Real subprocesses, mocked LLM** — most valuable test in the suite. |
| `test_e2e_generation_budgetzero.py` | Same shape, against `examples/budgetzero.yaml`. Skipped unless `RUN_LIVE_LLM=1`. |
| `test_smoke_integration.py` | Smoke step against `tests/fixtures/tiny-vite-app/`. End-to-end: dev server start → health poll → playwright run → cleanup. |

### Fixtures

- `tests/fixtures/tiny-vite-app/` — 50-line React+Vite app with two routes, two `data-testid`s. Pinned `package.json`, top-level `node_modules` excluded from cleanup. Hermetic — no network, no BudgetZero dependency.
- `tests/fixtures/golden_outputs/` — committed reference outputs for `examples/minimal.yaml`. Regenerated by `make refresh-goldens`.

### Out of scope for automated tests

- LLM output quality — that's what DeepEval's `evaluate` node does at runtime.
- Real BudgetZero in CI — network-dependent and brittle. Manual `make demo` target for humans.

---

## 8. Open questions for spec review

None outstanding. All five sections approved during the brainstorming session. Listed for the user's review of this written spec:

- Repo path: `~/Desktop/llm-ai-projects/langgraph-playwright-ts-framework-generator/`
- Python package name: `qa_framework_generator_ts`
- DeepEval threshold: `0.7` (matches Java generator)
- Max repair attempts: `3` (matches Java generator)
- Smoke-step dev-server health-poll timeout: `30s`
- Subprocess timeout for static validators: `120s`
- File-size cap for repair path: `50 KB`
- Default browsers when YAML omits the field: `[chromium, firefox, webkit, mobile-chrome]`

Each of these has a default chosen above; flagging here for explicit sign-off during user review.

---

## 9. Reference materials

- Existing Java generator: `~/Desktop/llm-ai-projects/langgraph-selenium-testng-framework-generator/`
- Target app: `~/Desktop/llm-ai-projects/budgetzero-web/` (cloned 2026-05-28)
- Playwright best practices: https://playwright.dev/docs/best-practices (locator strategy, web-first assertions, fixtures, projects, parallelism, network mocking, trace viewer, CI configuration, anti-patterns)
