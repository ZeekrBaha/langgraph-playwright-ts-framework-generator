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


def test_role_locator_without_name_renders_correctly():
    """Regression test: bare role locator (no name) must not crash."""
    out = render_page_object(
        class_name="X",
        url="/x",
        elements=[{"name": "main", "locator": {"strategy": "role", "role": "main"}}],
        actions=[],
    )
    assert "getByRole('main')" in out
    assert "{ name:" not in out  # no empty name block


def test_fill_with_interpolation_uses_backticks():
    """Regression test: fill with {var} must produce a template literal."""
    out = render_page_object(
        class_name="Y",
        url="/",
        elements=[{"name": "input", "locator": {"strategy": "testid", "value": "i"}}],
        actions=[{
            "name": "type",
            "params": [{"name": "txt", "type": "string"}],
            "steps": [{"do": "fill", "target": "input", "value": "{txt}"}],
        }],
    )
    assert "await this.input.fill(`${txt}`);" in out
    assert "String(" not in out  # no leftover String() wrapper


def test_fill_with_literal_string_no_interpolation():
    """Regression test: fill with plain string uses JSON-quoted literal."""
    out = render_page_object(
        class_name="Z",
        url="/",
        elements=[{"name": "input", "locator": {"strategy": "testid", "value": "i"}}],
        actions=[{
            "name": "type",
            "params": [],
            "steps": [{"do": "fill", "target": "input", "value": "hello"}],
        }],
    )
    assert 'await this.input.fill("hello");' in out
