"""CLI entrypoint and command registration."""

from __future__ import annotations

import click

from judgement_ai import __version__
from judgement_ai.cli.commands.export_csv import export_csv
from judgement_ai.cli.commands.grade import grade


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="judgement-ai")
def main() -> None:
    """Entry point for the judgement-ai CLI."""


main.add_command(grade)
main.add_command(export_csv)
