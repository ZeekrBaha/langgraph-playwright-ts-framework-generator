from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from qa_framework_generator_ts.cli import main


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_invokes_graph_with_config_path(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "done"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml"])
    assert result.exit_code == 0
    g.invoke.assert_called_once()
    sent_state = g.invoke.call_args.args[0]
    assert sent_state["config_path"] == "examples/minimal.yaml"
    assert sent_state["smoke_enabled"] is False


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_smoke_flag_enables_smoke(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "done"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml", "--smoke"])
    assert result.exit_code == 0
    sent_state = g.invoke.call_args.args[0]
    assert sent_state["smoke_enabled"] is True


@patch("qa_framework_generator_ts.cli.build_graph")
def test_cli_nonzero_exit_on_failed_status(build_graph):
    g = MagicMock()
    g.invoke = MagicMock(return_value={"status": "failed"})
    build_graph.return_value = g
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "examples/minimal.yaml"])
    assert result.exit_code != 0
