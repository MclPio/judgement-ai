"""Main grading CLI command."""

from __future__ import annotations

from pathlib import Path

import click

from judgement_ai.cli.common import (
    build_fetcher,
    build_grader,
    config_path,
    config_section,
    default_failure_log_path,
    load_queries,
    prepare_output_files,
    resolve_output_path,
    validate_raw_output_path,
)
from judgement_ai.config import load_config
from judgement_ai.output import write_csv_export
from judgement_ai.progress import TerminalProgressReporter
from judgement_ai.results_io import load_json_results


@click.command()
@click.option(
    "--config",
    "config_path_value",
    type=click.Path(exists=True, path_type=Path),
    help="Optional YAML config file.",
)
@click.option(
    "--queries",
    "queries_path",
    type=click.Path(exists=True, path_type=Path),
    help="Text or CSV file containing queries to grade.",
)
@click.option(
    "--results-file",
    "results_file",
    type=click.Path(exists=True, path_type=Path),
    help="JSON file containing pre-fetched results.",
)
@click.option("--model", "model_name", type=str, help="LLM model name.")
@click.option("--base-url", type=str, help="OpenAI-compatible base URL.")
@click.option("--api-key", default=None, help="LLM provider API key.")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    help="Canonical raw judgments JSON output path. Defaults to a safe local path when omitted.",
)
@click.option(
    "--csv-output",
    "csv_output_path",
    type=click.Path(path_type=Path),
    help="Optional CSV export path derived from the canonical JSON output.",
)
@click.option("--domain", "domain_context", type=str, help="Optional domain context.")
@click.option("--workers", "max_workers", type=int, help="Maximum concurrent workers.")
@click.option("--passes", type=int, help="Number of grading passes per item.")
@click.option("--temperature", type=float, help="Sampling temperature for the LLM.")
@click.option("--request-timeout", type=float, help="Provider request timeout in seconds.")
@click.option(
    "--max-attempts",
    type=int,
    help="Total attempts per item before logging a failure.",
)
@click.option(
    "--provider",
    type=click.Choice(["auto", "ollama", "openai_compatible"]),
    help="Provider mode.",
)
@click.option(
    "--response-mode",
    type=click.Choice(["json_schema", "text"]),
    help="Preferred response mode for the provider.",
)
@click.option("--think/--no-think", default=None, help="Provider thinking toggle when supported.")
@click.option(
    "--prompt-file",
    type=click.Path(exists=True, path_type=Path),
    help="Optional custom prompt template.",
)
@click.option("--resume", is_flag=True, default=False, help="Resume from an existing output file.")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing output files without prompting.",
)
def grade(
    config_path_value: Path | None,
    queries_path: Path | None,
    results_file: Path | None,
    model_name: str | None,
    base_url: str | None,
    api_key: str | None,
    output_path: Path | None,
    csv_output_path: Path | None,
    domain_context: str | None,
    max_workers: int | None,
    passes: int | None,
    temperature: float | None,
    request_timeout: float | None,
    max_attempts: int | None,
    provider: str | None,
    response_mode: str | None,
    think: bool | None,
    prompt_file: Path | None,
    resume: bool,
    force: bool,
) -> None:
    """Run a grading pass."""
    config = load_config(config_path_value) if config_path_value else {}
    search_config = config_section(config, "search")
    llm_config = config_section(config, "llm")
    grading_config = config_section(config, "grading")
    output_config = config_section(config, "output")

    queries_source = queries_path or config_path(config, "queries")
    if queries_source is None:
        raise click.UsageError("Provide --queries or set queries in the config file.")

    queries = load_queries(queries_source)
    if not queries:
        raise click.UsageError("No queries were found in the provided queries file.")

    fetcher = build_fetcher(
        results_file=results_file or config_path(search_config, "results_file"),
    )

    final_output_path, output_path_was_defaulted = resolve_output_path(
        output_path=output_path,
        output_config=output_config,
        resume=resume,
    )
    validate_raw_output_path(final_output_path)
    final_csv_output_path = csv_output_path or config_path(output_config, "csv_path")
    failed_log_path = default_failure_log_path(final_output_path)
    prepare_output_files(
        output_path=final_output_path,
        failed_log_path=failed_log_path,
        csv_output_path=final_csv_output_path,
        resume=resume,
        force=force,
    )
    grader = build_grader(
        fetcher=fetcher,
        llm_config=llm_config,
        grading_config=grading_config,
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
        domain_context=domain_context,
        max_workers=max_workers,
        passes=passes,
        temperature=temperature,
        request_timeout=request_timeout,
        max_attempts=max_attempts,
        provider=provider,
        response_mode=response_mode,
        think=think,
        prompt_file=prompt_file,
    )
    reporter = TerminalProgressReporter(
        label="grade",
        output_path=str(final_output_path),
        resume=resume,
    )

    if output_path_was_defaulted:
        click.echo(f"No output path provided. Using {final_output_path}.")

    results = grader.grade(
        queries=queries,
        resume_from=final_output_path if resume else None,
        failed_log_path=failed_log_path,
        output_path=final_output_path,
        progress_callback=reporter,
    )

    if final_csv_output_path is not None:
        all_results = load_json_results(final_output_path)
        write_csv_export(all_results, final_csv_output_path)

    summary = grader.last_summary
    click.echo(
        "Completed grading run: "
        f"{summary['successes']} successes, "
        f"{summary['failures']} failures, "
        f"{summary['skipped']} skipped."
    )
    click.echo(f"Wrote canonical raw judgments to {final_output_path}.")
    if resume:
        click.echo(
            "Resume mode reused existing raw judgments "
            f"and skipped {summary['skipped']} items."
        )
    if final_csv_output_path is not None:
        click.echo(f"Exported CSV to {final_csv_output_path}.")
    else:
        suggested_export_path = final_output_path.with_suffix(".csv")
        click.echo(
            "Need CSV later? "
            "Run `judgement-ai export-csv "
            f"--input {final_output_path} --output {suggested_export_path}`."
        )
    click.echo(f"Wrote {len(results)} new results in this run.")
    if summary["failures"] > 0:
        click.echo(f"Failure details were written to {failed_log_path}.")
