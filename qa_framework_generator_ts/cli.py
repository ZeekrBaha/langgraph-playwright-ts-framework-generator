from __future__ import annotations

import sys

import click
from dotenv import load_dotenv

from qa_framework_generator_ts.graph import build_graph


@click.command()
@click.option("--config", required=True, help="Path to YAML config.")
@click.option("--output-dir", default=None, help="Override output_dir from YAML.")
@click.option("--smoke", is_flag=True, default=False, help="Run live smoke step against target app.")
@click.option("--no-cleanup", is_flag=True, default=False, help="Skip cleanup of stale files.")
def main(config: str, output_dir: str | None, smoke: bool, no_cleanup: bool):
    """Generate a Playwright/TypeScript test framework from a YAML spec."""
    load_dotenv()
    initial = {
        "config_path": config,
        "output_dir": output_dir,
        "smoke_enabled": smoke,
    }
    graph = build_graph()
    final_state = graph.invoke(initial)
    status = final_state.get("status") if isinstance(final_state, dict) else final_state.status
    click.echo(f"Done. status={status}")
    if status not in ("done",):
        sys.exit(1)
