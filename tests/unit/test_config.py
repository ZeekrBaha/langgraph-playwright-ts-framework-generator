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
