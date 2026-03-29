"""Thin Click CLI over the library."""

from __future__ import annotations

from pathlib import Path

import click

from judgement_ai.fetcher import ElasticsearchFetcher, FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.output import write_json, write_quepid_csv


@click.group()
def main() -> None:
    """Entry point for the judgement-ai CLI."""


@main.command()
@click.option(
    "--queries",
    "queries_path",
    type=click.Path(exists=True, path_type=Path),
    required=True,
)
@click.option("--elasticsearch", "elasticsearch_url", type=str)
@click.option("--results-file", "results_file", type=click.Path(exists=True, path_type=Path))
@click.option("--model", "model_name", required=True)
@click.option("--base-url", default="https://api.openai.com/v1", show_default=True)
@click.option("--api-key", default=None)
@click.option("--output", "output_path", type=click.Path(path_type=Path), required=True)
@click.option(
    "--output-format",
    type=click.Choice(["quepid_csv", "json"]),
    default="quepid_csv",
    show_default=True,
)
def grade(
    queries_path: Path,
    elasticsearch_url: str | None,
    results_file: Path | None,
    model_name: str,
    base_url: str,
    api_key: str | None,
    output_path: Path,
    output_format: str,
) -> None:
    """Run a basic grading pass."""
    queries = [
        line.strip()
        for line in queries_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if elasticsearch_url:
        fetcher = ElasticsearchFetcher(url=elasticsearch_url)
    elif results_file:
        fetcher = FileResultsFetcher(path=results_file)
    else:
        raise click.UsageError("Provide either --elasticsearch or --results-file.")

    grader = Grader(
        fetcher=fetcher,
        llm_base_url=base_url,
        llm_api_key=api_key,
        llm_model=model_name,
    )
    results = grader.grade(queries=queries)

    if output_format == "json":
        write_json(results, output_path)
    else:
        write_quepid_csv(results, output_path)
