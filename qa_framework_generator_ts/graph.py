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
