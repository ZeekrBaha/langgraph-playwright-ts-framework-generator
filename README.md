# LangGraph Playwright TypeScript Framework Generator

A Python LangGraph application that generates production-grade **Playwright + TypeScript** end-to-end test frameworks from a single YAML config file — with LLM-powered generation, DeepEval quality gates, self-repair loops, an optional live smoke step against the target app, and CI scaffolding baked in.

You describe your target application (pages, elements, flows, browsers). The generator produces a standalone TypeScript project with the Playwright **fixtures + Page Object Model** pattern, multi-browser projects, sharded GitHub Actions CI, trace-on-first-retry, ESLint rules that forbid `page.waitForTimeout` — validates it, scores it with DeepEval, repairs any failures, and reports exactly what it built.

Sibling project to [`langgraph-selenium-testng-framework-generator`](https://github.com/ZeekrBaha/langgraph-selenium-testng-framework-generator). Same 12-node LangGraph topology, different target stack.

---

## What It Generates

| Artifact | Description |
|---|---|
| `package.json` | Pinned `@playwright/test`, ESLint, TypeScript devDependencies; `test` / `test:ui` / `test:headed` / `lint` scripts |
| `tsconfig.json` | Strict mode, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, ES2022 target, `Bundler` resolution |
| `playwright.config.ts` | `fullyParallel: true`, `trace: 'on-first-retry'`, `video: 'retain-on-failure'`, `screenshot: 'only-on-failure'`, multi-browser projects from YAML |
| `eslint.config.js` | `@typescript-eslint/no-floating-promises: error`, `await-thenable: error`, custom `no-restricted-syntax` rule that **rejects `page.waitForTimeout`** |
| `.github/workflows/test.yml` | GitHub Actions: Node 20, shard matrix `[1,2,3,4]`, `--with-deps` install only for the browsers in YAML, artifact upload on failure |
| `src/helpers/selectors.ts` | Typed `TESTID` const object — every YAML `testid` locator surfaced as a constant token for spec-level reuse |
| `src/helpers/money.ts` | `parseMoney` / `formatMoney` utilities (en-US locale) for assertion targets in finance apps |
| `src/pages/<Page>.ts` | **LLM-generated** Page Object class per YAML page: `constructor(private readonly page: Page)`, `readonly` Locator field per element, async method per action, deterministic `goto()` |
| `src/fixtures.ts` | **LLM-generated** `test.extend<Fixtures>` block: one camelCase fixture per page class, `await use(new XPage(page))` factory; re-exports `expect` so specs import only from `../src/fixtures` |
| `specs/<flow>.spec.ts` | **LLM-generated** spec per YAML flow: web-first `await expect(locator).toX(...)` assertions, every step wrapped in `await test.step('label', ...)`, optional `test.describe.configure({ tag: [...] })` |
| `README.md` | Per-project quick-start with `npm install` / `npx playwright install` / `npm test` |
| `GENERATION_REPORT.md` | File list, validation results, DeepEval scores, repair attempts, smoke step status |

---

## Architecture

### LangGraph pipeline

```
YAML Config
    │
    ▼
┌─────────────────┐
│ load_config     │  Reads YAML, validates with Pydantic
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ requirements    │  LLM: normalises raw input into structured requirements
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ blueprint       │  LLM: decides every generated file, class name, fixture name
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ render_static   │  Jinja2: package.json, tsconfig, playwright.config, eslint,
│                 │  CI workflow, helpers, README
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ generate_pages  │  LLM: structured JSON → TS page objects + fixtures + specs
│                 │  PageObjectOutput / TestCaseOutput via function calling
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ evaluate        │  DeepEval GEval: scores page objects and specs
│                 │  PageObjectQualityTS + SpecQualityTS metrics
│                 │  Routes to repair if score < threshold (default 0.7)
└────────┬────────┘
         │
    pass │ fail
         │    └──────────────────────┐
         ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ write_files     │         │ repair          │  Bounded: max 3 attempts
└────────┬────────┘         │                 │  Per-file targeted prompt
         │                  │  LLM: rewrites  │  50 KB size cap
         ▼                  │  failed files   │  is_stuck() detection
┌─────────────────┐         └────────┬────────┘
│ static_validate │  tsc --noEmit, eslint, playwright test --list │
│                 │  short-circuits on first failure              │
│                 │  head-and-tail truncated stderr (3 KB cap)    │
└────────┬────────┘                  │
    pass │ fail ──────────────────────┘
         ▼
┌─────────────────┐
│ smoke_validate  │  Optional (--smoke flag): npm run dev on target,
│                 │  health-probe loop (30s), npx playwright test --reporter=json,
│                 │  cleanup dev-server in try/finally
└────────┬────────┘
    pass │ fail ──────────────────▶ repair
         ▼
┌─────────────────┐
│ review          │  LLM checklist: getBy* only, web-first assertions,
│                 │  fixtures pattern, no waitForTimeout, no floating promises
└────────┬────────┘
    pass │ fail ──────────────────▶ repair
         ▼
┌─────────────────┐
│ final_report    │  Writes GENERATION_REPORT.md; status "done" only if all
│                 │  validations passed — "failed" if failures remain after
│                 │  repair exhaustion (⚠ see Known Issues)
└─────────────────┘
```

### Graph routing

```
load_config → requirements → blueprint → render_static → generate_pages
    → evaluate ──pass──▶ write_files → static_validate ──pass──▶ smoke_validate ──pass──▶ review
         │                                   │                          │                       │
        fail                               fail                       fail                    fail
         └───────────────────────────────▶ repair ◀──────────────────────────────────────────┘
                                             │
                                attempts < max_attempts
                                             │
                                     → static_validate (loop)
                                             │
                                    attempts >= max_attempts
                                             │
                                     → final_report
```

### Generated TypeScript framework structure

```
<output_dir>/
├── package.json
├── tsconfig.json
├── playwright.config.ts
├── eslint.config.js
├── .gitignore
├── .github/workflows/test.yml
├── src/
│   ├── helpers/
│   │   ├── selectors.ts            ← Typed testid tokens, one per YAML testid locator
│   │   └── money.ts                ← Currency parse/format helpers (en-US)
│   ├── pages/                      ← LLM-generated from pages: in YAML
│   │   ├── BudgetPage.ts           ← class BudgetPage { constructor(private readonly page: Page) ... }
│   │   ├── TransactionsPage.ts
│   │   └── ReportsPage.ts
│   └── fixtures.ts                 ← LLM-generated: test.extend<Fixtures>({...}) for all pages
├── specs/                          ← LLM-generated from flows: in YAML
│   ├── budgetsmoke.spec.ts         ← test.describe('BudgetSmoke', () => { test('...', async ({ budgetPage }) => { ... } })
│   ├── reportssmoke.spec.ts
│   └── transactionssmoke.spec.ts
├── README.md                       ← Per-project quick-start
└── GENERATION_REPORT.md            ← Files, validation results, repair attempts
```

---

## Tech Stack

### Python generator

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph, conditional edges, Pydantic state schema) |
| LLM generation | LangChain OpenAI (`ChatOpenAI` + `with_structured_output(method="function_calling")`) |
| LLM evaluation | DeepEval (`GEval` — `PageObjectQualityTS`, `SpecQualityTS`) |
| Config validation | Pydantic v2 (discriminated unions, cross-ref validators) |
| Template rendering | Jinja2 (`StrictUndefined`, `FileSystemLoader`) |
| Config format | PyYAML |
| CLI | Click (`--config`, `--output-dir`, `--smoke`, `--no-cleanup`) |
| Environment | python-dotenv |
| Tests | pytest + pytest-mock + syrupy |
| Python | 3.12+ |

### Generated TypeScript framework

| Layer | Technology |
|---|---|
| Test runner | Playwright 1.60+ |
| Language | TypeScript 5.5+ (strict mode, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) |
| Module system | ES2022 + `moduleResolution: "Bundler"` |
| Lint | ESLint 9 + `@typescript-eslint` (`no-floating-promises`, `await-thenable`, custom `no-restricted-syntax`) |
| Test pattern | **Fixtures + Page Object Model hybrid** (Playwright's current best practice) |
| Browsers | Chromium, Firefox, WebKit, Mobile Chrome (Pixel 5), Mobile Safari (iPhone 13) — selectable per project |
| Parallelism | `fullyParallel: true` + sharded CI matrix |
| Reporting | `list` locally, `github` + `html` in CI, `playwright-report/` artifact on failure |
| Tracing | `trace: 'on-first-retry'`, `video: 'retain-on-failure'`, `screenshot: 'only-on-failure'` |
| CI | GitHub Actions (Node 20, `--shard=${{ matrix.shard }}/4`) |

---

## Project Structure

```
langgraph-playwright-ts-framework-generator/
├── pyproject.toml
├── .env.example
├── README.md
├── qa_framework_generator_ts/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                      ← Click CLI: qa-gen-ts command
│   ├── config.py                   ← Pydantic models + load_config()
│   ├── state.py                    ← GeneratorState (LangGraph schema)
│   ├── graph.py                    ← StateGraph definition and routing
│   ├── llm.py                      ← ChatOpenAI factory, MissingAPIKeyError
│   ├── models.py                   ← LLM output schemas (PageObjectOutput, TestCaseOutput, ...)
│   ├── prompts.py                  ← Prompt builders + LOCATOR_HIERARCHY + FORBIDDEN_PATTERNS
│   ├── renderer.py                 ← Jinja2 renderer (static + page-object + fixtures + spec)
│   ├── evaluator.py                ← DeepEval GEval scoring with TS-specific criteria
│   ├── validators.py               ← Static (tsc/eslint/playwright list) + smoke_validate
│   ├── repair.py                   ← Per-file LLM repair, size cap, is_stuck detection
│   ├── file_writer.py              ← Safe writer with cleanup honoring ignore patterns
│   └── templates/
│       └── ts/
│           ├── package.json.j2
│           ├── tsconfig.json.j2
│           ├── playwright.config.ts.j2
│           ├── eslint.config.js.j2
│           ├── gitignore.j2
│           ├── ci-workflow.yml.j2
│           ├── helpers-selectors.ts.j2
│           ├── helpers-money.ts.j2
│           ├── README.md.j2
│           ├── page-object.ts.j2       ← LLM-output template
│           ├── fixtures.ts.j2          ← LLM-output template
│           └── spec.ts.j2              ← LLM-output template
├── tests/
│   ├── unit/
│   │   ├── test_state.py
│   │   ├── test_config.py
│   │   ├── test_file_writer.py
│   │   ├── test_renderer_static.py
│   │   ├── test_renderer_dynamic.py
│   │   ├── test_validators_static.py
│   │   ├── test_validators_smoke.py
│   │   ├── test_llm.py
│   │   ├── test_models.py
│   │   ├── test_prompts.py
│   │   ├── test_evaluator.py
│   │   ├── test_repair.py
│   │   ├── test_graph_routes.py
│   │   └── test_cli.py
│   ├── integration/
│   │   ├── test_e2e_generation_minimal.py     ← Full graph with mocked LLM
│   │   └── test_smoke_integration.py          ← Real subprocess vs tiny-vite-app
│   └── fixtures/
│       ├── valid_minimal.yaml
│       ├── invalid_css_locator.yaml
│       ├── invalid_dup_page.yaml
│       ├── invalid_flow_ref.yaml
│       └── tiny-vite-app/                     ← Hermetic React+Vite smoke target
├── examples/
│   ├── minimal.yaml                ← 1 page / 1 flow
│   └── budgetzero.yaml             ← 7 pages / 3 flows (real-world demo)
├── playwright-ts-framework-output/  ← Sample generated framework (live LLM run)
└── docs/
    └── superpowers/
        ├── specs/
        │   └── 2026-05-28-langgraph-playwright-ts-generator-design.md
        └── plans/
            └── 2026-05-28-langgraph-playwright-ts-generator.md
```

---

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- `OPENAI_API_KEY` — required for LLM-backed nodes (requirements, blueprint, generate, evaluate, review, repair)
- Node.js 20+ — required only if you run the optional `--smoke` step against a live target app

### Install

```bash
git clone https://github.com/ZeekrBaha/langgraph-playwright-ts-framework-generator
cd langgraph-playwright-ts-framework-generator

uv venv && uv pip install -e ".[dev]"

# Configure API key
cp .env.example .env
# Edit .env — set OPENAI_API_KEY=sk-...
```

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for LLM nodes and DeepEval scoring |
| `OPENAI_MODEL` | No | `gpt-4.1` | Model used for generation and evaluation |

> API keys are never written into generated TS files, generated reports, CI YAML, or README examples. `.env` is gitignored.

---

## Usage

### Generate a framework (full LangGraph pipeline)

```bash
uv run qa-gen-ts \
  --config examples/minimal.yaml \
  --output-dir playwright-ts-framework-output
```

### Generate against the BudgetZero canonical demo

```bash
# Clone the target app (open source React + Convex + Tailwind, 7 routes)
git clone https://github.com/ZeekrBaha/budgetzero-web ../budgetzero-web

uv run qa-gen-ts \
  --config examples/budgetzero.yaml \
  --output-dir playwright-ts-framework-output
```

### Generate AND run the produced suite against the live target

```bash
# Pre-req: budgetzero-web cloned at ../budgetzero-web with `npm install` already run

uv run qa-gen-ts \
  --config examples/budgetzero.yaml \
  --output-dir playwright-ts-framework-output \
  --smoke
```

The `--smoke` flag adds a real run of `npx playwright test --reporter=json` against the dev server defined in `target_app.start_command`. The dev server is started under `subprocess.Popen`, health-probed at `target_app.health_path` (30s timeout), and **always terminated** via `try/finally` even on exception.

### Skip stale-file cleanup

```bash
uv run qa-gen-ts \
  --config examples/minimal.yaml \
  --output-dir playwright-ts-framework-output \
  --no-cleanup
```

> ⚠ The `--no-cleanup` flag is currently parsed but not yet wired into the graph state. Cleanup always runs. See Known Issues.

### Run the generated Playwright framework

```bash
cd playwright-ts-framework-output

npm install
npx playwright install --with-deps chromium     # or chromium firefox webkit

# Run everything
npm test

# Run only smoke-tagged specs
npx playwright test --grep @smoke

# Run a single project (browser)
npx playwright test --project=chromium

# Run in UI mode (interactive)
npm run test:ui

# Run headed
npm run test:headed
```

### Run generator tests

```bash
# Fast suite (unit + mocked-LLM integration)
uv run pytest -v -m "not slow"

# Slow integration (real subprocess against tiny-vite-app fixture; needs npm)
uv run pytest -v -m slow

# Everything
uv run pytest -v
```

---

## Config Reference

```yaml
project_name: budgetzero-e2e                # Required. Used as npm name + import root.
package_name: budgetzero                    # Required. Same.
output_dir: ./budgetzero-output             # Default output location (overridable via --output-dir)

target_app:
  name: BudgetZero
  base_url: http://localhost:5173           # Used in playwright.config.ts BASE_URL fallback
  start_command: npm run dev                # Used by --smoke step only
  start_cwd: ../budgetzero-web              # Relative to output_dir; where start_command runs
  health_path: /                            # Polled until 200 before tests run

browsers:                                   # → playwright.config.ts projects[]
  - chromium
  - firefox                                 # webkit / mobile-chrome / mobile-safari also supported
  - webkit
  - mobile-chrome

pages:
  - name: BudgetPage                        # Generates BudgetPage.ts class
    url: /                                  # this.page.goto('/')
    elements:
      - name: heading                       # Field name in the page object
        locator:                            # Discriminated union by `strategy`:
          strategy: role                    #   role | testid | label | text | placeholder | altText | title
          role: heading                     #   role-specific: role + optional name
          name: "Budget"
      - name: categoryRowGroceries
        locator:
          strategy: testid
          value: category-row-groceries
    actions:
      - name: assignIncome
        params:
          - { name: amount, type: number }  # type: string | number | boolean
        steps:
          - { do: fill, target: incomeInput, value: "{amount}" }
          - { do: click, target: assignButton }   # do: click | fill | select | check | uncheck | hover | press

flows:
  - name: BudgetSmoke                       # Generates budgetsmoke.spec.ts
    tags: [smoke, budget]                   # → test.describe.configure({ tag: ['@smoke', '@budget'] })
    steps:
      - { page: BudgetPage, action: goto }                  # The implicit goto action
      - { page: BudgetPage, action: assignIncome, args: { amount: 500 } }
    assertions:
      - { "on": BudgetPage.heading, expect: toBeVisible }    # Note: "on" must be quoted (YAML 1.1 boolean trap)
      - { "on": BudgetPage.readyToAssign, expect: toHaveText, value: "$0" }
```

Supported `expect` values: `toBeVisible`, `toBeHidden`, `toHaveText`, `toContainText`, `toHaveValue`, `toHaveCount`, `toBeEnabled`, `toBeDisabled`.

**Why CSS and XPath are not options:** generated locators must use Playwright's user-facing API (`getByRole`, `getByLabel`, `getByText`, `getByTestId`, `getByPlaceholder`, `getByAltText`, `getByTitle`). CSS and XPath are rejected by the YAML schema, by the LLM prompts (explicit "NEVER use page.locator() with CSS selectors or XPath"), and by the DeepEval criteria. This is enforced in three independent layers because LLMs drift.

---

## Validation Gates

### Static validation

The `static_validate` node runs three subprocesses in sequence, short-circuiting on first failure. Skipped steps still produce a `ValidationResult` (passed=True with `"skipped: ..."` in output) so the graph routing remains clean.

| Check | Command | What it catches |
|---|---|---|
| `tsc` | `npx tsc --noEmit -p tsconfig.json` | Type errors, missing imports, fixture-name casing mismatches, undefined locators |
| `eslint` | `npx eslint .` | Floating promises, `page.waitForTimeout`, `no-restricted-syntax` violations |
| `playwright_list` | `npx playwright test --list` | Spec discovery failures, broken `import { test, expect }` paths |

All three have a 120s timeout. Non-zero exit produces a head-and-tail truncated stderr (1.5 KB + 1.5 KB joined by `…[truncated]…`) so reports don't bloat.

### Smoke validation (optional, `--smoke` flag)

| Failure path | Detection | Routing |
|---|---|---|
| **Dev server unhealthy** | `_wait_for_health()` returns False after 30s (probes `base_url + health_path` every 500ms; bails early if `proc.poll()` shows the dev server died) | One `ValidationResult(name="dev_server_unhealthy")`, **skip repair** (LLM can't fix the target app) |
| **Per-test failure** | Playwright JSON reporter `stats.unexpected > 0`; each failed spec parsed into `test_failure:<title>` result with file path + trimmed error message | Enters repair loop with concrete locator/assertion context |
| **Playwright crashed** | Non-zero exit with no parseable JSON | One `ValidationResult(name="smoke_crashed")`, skip repair |

The dev server is always terminated via `try/finally` — first `terminate()` with 5s grace, then `kill()` with 2s grace. Verified by `test_smoke_terminates_devserver_even_on_exception` and the real-subprocess `test_smoke_integration.py`.

---

## DeepEval Quality Gates

After LLM-generated page objects and specs are produced, the `evaluate` node scores each file against two `GEval` metrics before writing to disk:

| Metric | Evaluated on | Criteria |
|---|---|---|
| `PageObjectQualityTS` | Every `src/pages/*.ts` file | Class name matches YAML, `constructor(private readonly page: Page)`, every YAML element appears as a `readonly Locator`, locators built from `getBy*` only (no CSS/XPath), every YAML action as async method, no `page.waitForTimeout` / `setTimeout` / `locator.waitFor` before clicks |
| `SpecQualityTS` | Every `specs/*.spec.ts` file | Imports `test` and `expect` from `../src/fixtures` (not `@playwright/test`), every YAML step wrapped in `await test.step('label', async () => { ... })`, every assertion is web-first `await expect(locator).toX(...)`, no `expect(await locator.isVisible()).toBe(true)` anti-pattern, no floating promises, tags via `test.describe.configure({ tag })` |

Files that score below `--eval-threshold` (default `0.7`) are sent to the LLM repair loop before being written to disk. Scores are included in `GENERATION_REPORT.md`.

---

## Multi-browser Projects (the Playwright analog to Selenium Grid)

`playwright.config.ts` is generated with a `projects[]` array driven by the `browsers:` list in YAML. Each entry maps to a Playwright `devices[...]` profile:

| YAML browser | Playwright project | Device profile |
|---|---|---|
| `chromium` | Desktop Chrome | `devices['Desktop Chrome']` |
| `firefox` | Desktop Firefox | `devices['Desktop Firefox']` |
| `webkit` | Desktop Safari | `devices['Desktop Safari']` |
| `mobile-chrome` | Pixel 5 | `devices['Pixel 5']` |
| `mobile-safari` | iPhone 13 | `devices['iPhone 13']` |

Run a single browser locally without changing the generated code:

```bash
npx playwright test --project=chromium
npx playwright test --project=mobile-chrome --grep @smoke
```

CI sharding is automatic — the generated workflow runs `--shard=${{ matrix.shard }}/4` so 4 GitHub Actions runners execute roughly 25% of the spec count each.

---

## Sample Generated Output

`playwright-ts-framework-output/` in this repo contains a live LLM run against `examples/minimal.yaml`. It demonstrates exactly what comes out of the pipeline.

`src/pages/HomePage.ts`:

```ts
import { Page, Locator } from '@playwright/test';

export class HomePage {
  constructor(private readonly page: Page) {}

  readonly heading: Locator = this.page.getByRole('heading', { name: 'Welcome' });

  async goto(): Promise<void> {
    await this.page.goto('/');
  }
}
```

`src/fixtures.ts`:

```ts
import { test as base, expect } from '@playwright/test';
import { HomePage } from './pages/HomePage';

type Fixtures = {
  homePage: HomePage;
};

export const test = base.extend<Fixtures>({
  homePage: async ({ page }, use) => {
    await use(new HomePage(page));
  },
});

export { expect };
```

The actual `specs/homeflow.spec.ts` from the live run currently has a casing drift bug from the LLM (`{ HomePage }` instead of `{ homePage }`) — see Known Issues. This is exactly the kind of bug `tsc --noEmit` catches in `static_validate` when `node_modules` is available in the output dir.

---

## Known Issues

These are tracked for follow-up PRs. Most surfaced from the final overall code review and the first live LLM run.

### P1 — Silent "done" on repair exhaustion

`final_report_node` reports `status="done"` when `state.validation_results` is empty, but `repair_node` clears that list on every pass. When `repair_attempts >= max_repair_attempts`, `route_after_repair` jumps directly to `final_report` and the empty list reads as zero failures. The `GENERATION_REPORT.md` still shows `Status: repairing` and `Repair attempts: 3` (the truth), but the CLI exits 0 (the lie). Fix: track the last non-empty failure set in state, or have `final_report_node` inspect `repair_attempts == max_repair_attempts` as a failure signal.

### P2 — LLM casing drift in generated specs

The LLM occasionally destructures fixtures with the wrong casing (`{ HomePage }` instead of `{ homePage }`) and references them in PascalCase throughout the spec body. The `fixtures.ts` template uses camelCase deterministically, so import/usage mismatch produces a `tsc` error. With `node_modules` installed in the output dir, `static_validate` catches it and routes to repair — but in fresh runs the toolchain check fails for missing-toolchain reasons before catching the actual TS error. Fix: tighten the spec prompt to be explicit about camelCase fixture naming, or post-process the LLM output to lower-case the first character of fixture references.

### P2 — `ActionStep.target` not validated against element names

A YAML action step can reference a non-existent element (e.g. `target: ttle` instead of `title`) and pass config-load time silently. The template then emits `this.ttle.click()` which only fails at `tsc` time. Adding an `Action` validator that checks `step.target ∈ {e.name for e in page.elements}` would catch this at YAML load.

### P2 — `goto` accepted as a page action name

If a user defines `actions: [{name: goto, ...}]`, the page-object template emits two `async goto()` methods, a TS error. The `RESERVED_ELEMENT_NAMES` guard covers element names only; action names need the same check.

### P3 — `--no-cleanup` flag is a no-op

`cli.py` parses `--no-cleanup` but the flag is never threaded into `GeneratorState` and `write_files_node` always calls `write_files(..., force=True)` with the default `cleanup=True`. Add a `cleanup_enabled` state field and a constructor argument.

### P3 — `is_stuck()` is dead code

`repair.is_stuck()` is implemented and unit-tested but never called from `graph.py`. The only runaway protection today is the `max_repair_attempts` cap. Wire it into `route_after_repair` using a `validation_history: list[list[ValidationResult]]` field in state, or remove the function and its test.

### P3 — `smoke_log` state field never populated

`GeneratorState.smoke_log: Optional[str]` is defined but no node writes to it. Either populate it from the dev-server stdout/stderr or remove the field.

### P3 — Locator union lacks explicit discriminator

`Locator = Union[RoleLocator, ValueLocator]` works correctly via Pydantic v2's smart-union disambiguation but produces noisy three-error stack traces when a CSS-strategy locator is rejected. Adding `Annotated[Union[...], Field(discriminator="strategy")]` makes the intent explicit and produces a single clean error.

### P4 — Stale version floors in pyproject.toml

`langgraph>=0.2.0` resolves to 1.2.2 (loose floor over a major version boundary); `deepeval>=1.0` resolves to 4.0.5 (4-major-version jump). The lockfile pins correctly, but the floors should be tightened to `>=1.0.0` and `>=4.0` respectively.

### P4 — Jinja whitespace artifact in generated TS

`_env()` uses `trim_blocks=False, lstrip_blocks=False` which produces 3-4 blank lines between each `readonly` Locator field. The output is syntactically valid but visually noisy. `trim_blocks=True` would fix it.

---

## Plan & Spec

The implementation was built via the [superpowers](https://github.com/obra/superpowers) workflow — brainstorming → spec → plan → subagent-driven execution. The full design and plan live in:

- `docs/superpowers/specs/2026-05-28-langgraph-playwright-ts-generator-design.md`
- `docs/superpowers/plans/2026-05-28-langgraph-playwright-ts-generator.md`

22 implementation tasks, TDD throughout, 72 passing tests (69 unit + 1 fast integration + 2 real-subprocess slow integration).

---

## Reference

The generated framework follows current Playwright best practices: web-first assertions, the fixtures + POM hybrid pattern, multi-browser projects, sharded CI, `trace: 'on-first-retry'`, ESLint rules forbidding the well-known anti-patterns. The generator adds LLM-powered generation, DeepEval quality scoring, structured prompts, per-file repair, an optional live smoke step, and overwrite-safe file writing on top of this foundation.
