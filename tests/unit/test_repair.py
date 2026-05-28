from unittest.mock import patch, MagicMock

from qa_framework_generator_ts.repair import repair_files, FILE_TOO_LARGE_BYTES
from qa_framework_generator_ts.state import GeneratedFile, ValidationResult


def _mock_llm_returning(content: str):
    llm = MagicMock()
    response = MagicMock()
    response.content = content
    llm.invoke = MagicMock(return_value=response)
    return llm


@patch("qa_framework_generator_ts.repair.get_openai_chat_model")
def test_repair_files_rewrites_only_targeted_files(get_llm):
    get_llm.return_value = _mock_llm_returning("class Fixed {}")
    files = [
        GeneratedFile(path="src/pages/HomePage.ts", content="class HomePage {}", kind="typescript"),
        GeneratedFile(path="src/pages/Other.ts", content="class Other {}", kind="typescript"),
    ]
    failures = [
        ValidationResult(
            name="test_failure:HomePage broken",
            passed=False,
            output="locator timed out\nfile=src/pages/HomePage.ts",
            fix_hint="fix locator",
        )
    ]
    result = repair_files(files, failures)
    home = next(f for f in result if f.path == "src/pages/HomePage.ts")
    other = next(f for f in result if f.path == "src/pages/Other.ts")
    assert home.content == "class Fixed {}"
    assert other.content == "class Other {}"


@patch("qa_framework_generator_ts.repair.get_openai_chat_model")
def test_repair_files_skips_files_over_size_cap(get_llm):
    big_content = "x" * (FILE_TOO_LARGE_BYTES + 1)
    files = [GeneratedFile(path="src/pages/Big.ts", content=big_content, kind="typescript")]
    failures = [
        ValidationResult(name="tsc", passed=False, output="error in src/pages/Big.ts", fix_hint="")
    ]
    result = repair_files(files, failures)
    assert result[0].content == big_content  # unchanged
    get_llm.assert_not_called()


def test_repair_detects_stuck_state():
    from qa_framework_generator_ts.repair import is_stuck
    f1 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    f2 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    f3 = ValidationResult(name="tsc", passed=False, output="error TS2304")
    assert is_stuck([[f1], [f2], [f3]]) is True


def test_repair_not_stuck_when_output_changes():
    from qa_framework_generator_ts.repair import is_stuck
    f1 = ValidationResult(name="tsc", passed=False, output="error A")
    f2 = ValidationResult(name="tsc", passed=False, output="error B")
    f3 = ValidationResult(name="tsc", passed=False, output="error A")
    assert is_stuck([[f1], [f2], [f3]]) is False
