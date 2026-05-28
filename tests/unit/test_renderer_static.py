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
