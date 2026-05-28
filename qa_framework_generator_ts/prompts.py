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
    + "\n".join(
        f"  {i+1}. getBy{s[0].upper()}{s[1:]}(...)  [{s}]"
        for i, s in enumerate(LOCATOR_HIERARCHY)
    )
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
