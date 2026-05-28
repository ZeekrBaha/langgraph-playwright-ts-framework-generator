from __future__ import annotations

import re

from qa_framework_generator_ts.llm import get_openai_chat_model
from qa_framework_generator_ts.prompts import build_repair_prompt
from qa_framework_generator_ts.state import GeneratedFile, ValidationResult


FILE_TOO_LARGE_BYTES = 50 * 1024


def _failures_by_file(
    failures: list[ValidationResult],
    files: list[GeneratedFile],
) -> dict[str, list[ValidationResult]]:
    mapping: dict[str, list[ValidationResult]] = {f.path: [] for f in files}
    file_paths = list(mapping.keys())
    for failure in failures:
        text = f"{failure.name}\n{failure.output}"
        for path in file_paths:
            if path in text:
                mapping[path].append(failure)
    return mapping


def repair_files(
    files: list[GeneratedFile],
    failures: list[ValidationResult],
) -> list[GeneratedFile]:
    by_file = _failures_by_file(failures, files)
    if not any(by_file.values()):
        # No file-scoped failures; nothing to repair locally.
        return list(files)

    llm = None
    new_files: list[GeneratedFile] = []
    for f in files:
        targeted = by_file.get(f.path, [])
        if not targeted:
            new_files.append(f)
            continue
        if len(f.content.encode("utf-8")) > FILE_TOO_LARGE_BYTES:
            new_files.append(f)  # caller should regenerate from scratch
            continue
        if llm is None:
            llm = get_openai_chat_model()
        prompt = build_repair_prompt(
            file_path=f.path,
            file_content=f.content,
            failures=[t.model_dump() for t in targeted],
        )
        response = llm.invoke(prompt)
        new_content = response.content if hasattr(response, "content") else str(response)
        new_content = _strip_code_fence(new_content)
        new_files.append(GeneratedFile(path=f.path, content=new_content, kind=f.kind))
    return new_files


def _strip_code_fence(text: str) -> str:
    m = re.match(r"^```[\w]*\n(.*?)\n```\s*$", text.strip(), re.DOTALL)
    return m.group(1) if m else text


def is_stuck(history: list[list[ValidationResult]]) -> bool:
    """True if last three rounds have identical failure signatures (same name+output)."""
    if len(history) < 3:
        return False
    last_three = history[-3:]
    sig = lambda rs: tuple(sorted((r.name, r.output) for r in rs if not r.passed))
    a, b, c = (sig(rs) for rs in last_three)
    return a == b == c and len(a) > 0
