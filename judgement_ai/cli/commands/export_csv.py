"""CSV export CLI command."""

from __future__ import annotations

from pathlib import Path

import click

from judgement_ai.cli.common import (
    prepare_single_output_file,
    validate_csv_output_path,
    validate_raw_output_path,
)
from judgement_ai.output import write_csv_export
from judgement_ai.results_io import load_json_results


@click.command("export-csv")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Canonical raw judgments JSON file to export.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(path_type=Path),
    help="CSV output path.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing output files without prompting.",
)
def export_csv(
    input_path: Path,
    output_path: Path,
    force: bool,
) -> None:
    """Export canonical raw judgments JSON as CSV."""
    validate_raw_output_path(input_path)
    validate_csv_output_path(output_path)
    results = load_json_results(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepare_single_output_file(path=output_path, force=force)
    write_csv_export(results, output_path)

    click.echo(f"Loaded canonical raw judgments from {input_path}.")
    click.echo(f"Exported CSV to {output_path}.")
    click.echo(f"Wrote {len(results)} rows.")
