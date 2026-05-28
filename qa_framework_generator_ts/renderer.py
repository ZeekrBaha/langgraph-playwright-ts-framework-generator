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
