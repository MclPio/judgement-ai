"""Thin Click CLI over the library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from judgement_ai.config import load_config
from judgement_ai.fetcher import ElasticsearchFetcher, FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.progress import TerminalProgressReporter


@click.group()
def main() -> None:
    """Entry point for the judgement-ai CLI."""


@main.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--queries",
    "queries_path",
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--elasticsearch", "elasticsearch_url", type=str)
@click.option("--results-file", "results_file", type=click.Path(exists=True, path_type=Path))
@click.option("--model", "model_name", type=str)
@click.option("--base-url", type=str)
@click.option("--api-key", default=None)
@click.option("--output", "output_path", type=click.Path(path_type=Path))
@click.option(
    "--output-format",
    type=click.Choice(["quepid_csv", "json"]),
)
@click.option("--domain", "domain_context", type=str)
@click.option("--top-n", type=int)
@click.option("--workers", "max_workers", type=int)
@click.option("--passes", type=int)
@click.option("--request-timeout", type=float)
@click.option("--max-retries", type=int)
@click.option("--prompt-file", type=click.Path(exists=True, path_type=Path))
@click.option("--resume", is_flag=True, default=False)
def grade(
    config_path: Path | None,
    queries_path: Path | None,
    elasticsearch_url: str | None,
    results_file: Path | None,
    model_name: str | None,
    base_url: str | None,
    api_key: str | None,
    output_path: Path | None,
    output_format: str | None,
    domain_context: str | None,
    top_n: int | None,
    max_workers: int | None,
    passes: int | None,
    request_timeout: float | None,
    max_retries: int | None,
    prompt_file: Path | None,
    resume: bool,
) -> None:
    """Run a grading pass."""
    config = load_config(config_path) if config_path else {}

    queries_source = queries_path or _config_path(config, "queries")
    if queries_source is None:
        raise click.UsageError("Provide --queries or set queries in the config file.")

    queries = _load_queries(queries_source)
    if not queries:
        raise click.UsageError("No queries were found in the provided queries file.")

    search_config = _config_section(config, "search")
    llm_config = _config_section(config, "llm")
    grading_config = _config_section(config, "grading")
    output_config = _config_section(config, "output")

    fetcher = _build_fetcher(
        elasticsearch_url=elasticsearch_url or _config_str(search_config, "url"),
        results_file=results_file or _config_path(search_config, "results_file"),
        top_n=top_n or _config_int(search_config, "top_n") or 10,
    )

    final_output_path = output_path or _config_path(output_config, "path")
    if final_output_path is None:
        raise click.UsageError("Provide --output or set output.path in the config file.")

    final_output_format = output_format or _config_str(output_config, "format") or "quepid_csv"
    llm_model = model_name or _config_str(llm_config, "model")
    if not llm_model:
        raise click.UsageError("Provide --model or set llm.model in the config file.")

    llm_base_url = base_url or _config_str(llm_config, "base_url") or "https://api.openai.com/v1"
    scale_min = _config_int(grading_config, "scale_min")
    scale_max = _config_int(grading_config, "scale_max")
    scale_labels = grading_config.get("scale_labels")

    grader = Grader(
        fetcher=fetcher,
        llm_base_url=llm_base_url,
        llm_api_key=api_key if api_key is not None else _config_str(llm_config, "api_key"),
        llm_model=llm_model,
        domain_context=domain_context
        if domain_context is not None
        else _config_str(grading_config, "domain_context"),
        scale_min=scale_min if scale_min is not None else 0,
        scale_max=scale_max if scale_max is not None else 3,
        scale_labels=scale_labels if isinstance(scale_labels, dict) else None,
        max_workers=max_workers or _config_int(grading_config, "max_workers") or 10,
        passes=passes or _config_int(grading_config, "passes") or 1,
        max_retries=max_retries
        if max_retries is not None
        else _config_int(grading_config, "max_retries")
        or 3,
        request_timeout=request_timeout
        if request_timeout is not None
        else _config_float(grading_config, "request_timeout")
        or 60.0,
        prompt_template=str(prompt_file)
        if prompt_file is not None
        else _config_str(grading_config, "prompt_file"),
    )
    reporter = TerminalProgressReporter(label="grade")

    results = grader.grade(
        queries=queries,
        resume_from=final_output_path if resume else None,
        output_path=final_output_path,
        output_format=final_output_format,
        progress_callback=reporter,
    )

    click.echo(
        "Completed grading run: "
        f"{grader.last_summary['successes']} successes, "
        f"{grader.last_summary['failures']} failures, "
        f"{grader.last_summary['skipped']} skipped."
    )
    click.echo(f"Wrote {len(results)} new results to {final_output_path}.")


def _load_queries(path: Path) -> list[str]:
    """Load one query per line from a text file."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _build_fetcher(
    *,
    elasticsearch_url: str | None,
    results_file: Path | None,
    top_n: int,
):
    """Build the configured fetcher implementation."""
    if elasticsearch_url and results_file:
        raise click.UsageError("Choose either Elasticsearch or a results file, not both.")
    if elasticsearch_url:
        return ElasticsearchFetcher(url=elasticsearch_url, top_n=top_n)
    if results_file:
        return FileResultsFetcher(path=results_file)
    raise click.UsageError(
        "Provide either --elasticsearch/--results-file or configure search.url/search.results_file."
    )


def _config_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key, {})
    return value if isinstance(value, dict) else {}


def _config_str(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    return value if isinstance(value, str) else None


def _config_int(config: dict[str, Any], key: str) -> int | None:
    value = config.get(key)
    return value if isinstance(value, int) else None


def _config_path(config: dict[str, Any], key: str) -> Path | None:
    value = _config_str(config, key)
    return Path(value) if value else None


def _config_float(config: dict[str, Any], key: str) -> float | None:
    value = config.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None
