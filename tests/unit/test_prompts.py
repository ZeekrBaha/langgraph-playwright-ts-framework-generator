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
