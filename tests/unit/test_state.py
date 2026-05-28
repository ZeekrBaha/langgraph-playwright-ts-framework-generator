from qa_framework_generator_ts.state import GeneratedFile, GeneratorState, ValidationResult


def test_generator_state_defaults():
    state = GeneratorState(config_path="examples/minimal.yaml")
    assert state.config_path == "examples/minimal.yaml"
    assert state.output_dir is None
    assert state.generated_files == []
    assert state.validation_results == []
    assert state.repair_attempts == 0
    assert state.max_repair_attempts == 3
    assert state.eval_threshold == 0.7
    assert state.smoke_enabled is False
    assert state.smoke_log is None
    assert state.status == "pending"


def test_generated_file_round_trip():
    f = GeneratedFile(path="src/foo.ts", content="export {};", kind="typescript")
    assert f.path == "src/foo.ts"
    assert f.kind == "typescript"


def test_validation_result_failure_carries_hint():
    r = ValidationResult(name="tsc", passed=False, output="error TS2304", fix_hint="define the symbol")
    assert r.passed is False
    assert r.fix_hint == "define the symbol"
