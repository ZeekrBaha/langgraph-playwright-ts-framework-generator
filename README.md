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
