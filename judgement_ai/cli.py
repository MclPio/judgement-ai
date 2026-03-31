"""Thin Click CLI over the library."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import click

from judgement_ai import __version__
from judgement_ai.config import load_config
from judgement_ai.fetcher import ElasticsearchFetcher, FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.progress import TerminalProgressReporter


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="judgement-ai")
def main() -> None:
    """Entry point for the judgement-ai CLI."""


@main.command()
@click.option(
    "--config",
    "config_path",
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
    "--elasticsearch",
    "elasticsearch_url",
    type=str,
    help="Base Elasticsearch index URL, without /_search.",
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
    help="Output file path for judgments.",
)
@click.option(
    "--output-format",
    type=click.Choice(["quepid_csv", "json"]),
    help="Output format to write.",
)
@click.option("--domain", "domain_context", type=str, help="Optional domain context.")
@click.option("--top-n", type=int, help="Top N results to fetch from Elasticsearch.")
@click.option("--workers", "max_workers", type=int, help="Maximum concurrent workers.")
@click.option("--passes", type=int, help="Number of grading passes per item.")
@click.option("--request-timeout", type=float, help="Provider request timeout in seconds.")
@click.option("--max-retries", type=int, help="Attempts per item before logging a failure.")
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
    provider: str | None,
    response_mode: str | None,
    think: bool | None,
    prompt_file: Path | None,
    resume: bool,
    force: bool,
) -> None:
    """Run a grading pass."""
    config = load_config(config_path) if config_path else {}
    search_config = _config_section(config, "search")
    llm_config = _config_section(config, "llm")
    grading_config = _config_section(config, "grading")
    output_config = _config_section(config, "output")

    queries_source = queries_path or _config_path(config, "queries")
    if queries_source is None:
        raise click.UsageError("Provide --queries or set queries in the config file.")

    queries = _load_queries(queries_source)
    if not queries:
        raise click.UsageError("No queries were found in the provided queries file.")

    fetcher = _build_fetcher(
        elasticsearch_url=elasticsearch_url or _config_str(search_config, "url"),
        results_file=results_file or _config_path(search_config, "results_file"),
        top_n=top_n or _config_int(search_config, "top_n") or 10,
    )

    final_output_path = _require_output_path(
        output_path=output_path,
        output_config=output_config,
    )
    failed_log_path = _default_failure_log_path(final_output_path)
    _prepare_output_files(
        output_path=final_output_path,
        failed_log_path=failed_log_path,
        resume=resume,
        force=force,
    )

    final_output_format = _resolve_output_format(
        explicit_format=output_format,
        config_format=_config_str(output_config, "format"),
        output_path=final_output_path,
    )
    grader = _build_grader(
        fetcher=fetcher,
        llm_config=llm_config,
        grading_config=grading_config,
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
        domain_context=domain_context,
        max_workers=max_workers,
        passes=passes,
        request_timeout=request_timeout,
        max_retries=max_retries,
        provider=provider,
        response_mode=response_mode,
        think=think,
        prompt_file=prompt_file,
    )
    reporter = TerminalProgressReporter(label="grade")

    results = grader.grade(
        queries=queries,
        resume_from=final_output_path if resume else None,
        failed_log_path=failed_log_path,
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
    if grader.last_summary["failures"] > 0:
        click.echo(f"Failure details were written to {failed_log_path}.")


def _load_queries(path: Path) -> list[str]:
    """Load queries from a text file or CSV file."""
    if path.suffix.lower() == ".csv":
        return _load_queries_from_csv(path)
    return _load_queries_from_text(path)


def _load_queries_from_text(path: Path) -> list[str]:
    """Load one query per line from a text file."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_queries_from_csv(path: Path) -> list[str]:
    """Load queries from a CSV file."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            has_header = False

        if has_header:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                return []
            lowered = {name.lower(): name for name in reader.fieldnames}
            query_field = lowered.get("query")
            if query_field is not None:
                return [
                    value.strip()
                    for row in reader
                    if isinstance((value := row.get(query_field)), str) and value.strip()
                ]
            handle.seek(0)

        reader = csv.reader(handle)
        queries: list[str] = []
        for row in reader:
            if row and row[0].strip():
                queries.append(row[0].strip())
        return queries


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


def _config_bool(config: dict[str, Any], key: str) -> bool | None:
    value = config.get(key)
    return value if isinstance(value, bool) else None


def _require_output_path(*, output_path: Path | None, output_config: dict[str, Any]) -> Path:
    """Resolve the output path or raise a clear CLI error."""
    resolved = output_path or _config_path(output_config, "path")
    if resolved is None:
        raise click.UsageError("Provide --output or set output.path in the config file.")
    return resolved


def _build_grader(
    *,
    fetcher: ElasticsearchFetcher | FileResultsFetcher,
    llm_config: dict[str, Any],
    grading_config: dict[str, Any],
    model_name: str | None,
    base_url: str | None,
    api_key: str | None,
    domain_context: str | None,
    max_workers: int | None,
    passes: int | None,
    request_timeout: float | None,
    max_retries: int | None,
    provider: str | None,
    response_mode: str | None,
    think: bool | None,
    prompt_file: Path | None,
) -> Grader:
    """Build the grader from CLI arguments and config."""
    llm_model = model_name or _config_str(llm_config, "model")
    if not llm_model:
        raise click.UsageError("Provide --model or set llm.model in the config file.")

    scale_min = _config_int(grading_config, "scale_min")
    scale_max = _config_int(grading_config, "scale_max")
    scale_labels = grading_config.get("scale_labels")

    return Grader(
        fetcher=fetcher,
        llm_base_url=base_url or _config_str(llm_config, "base_url") or "https://api.openai.com/v1",
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
        provider=provider or _config_str(llm_config, "provider") or "auto",
        response_mode=response_mode or _config_str(grading_config, "response_mode") or "text",
        think=think if think is not None else _config_bool(llm_config, "think"),
        prompt_template=str(prompt_file)
        if prompt_file is not None
        else _config_str(grading_config, "prompt_file"),
    )


def _default_failure_log_path(output_path: Path) -> Path:
    """Return the default failure log path beside the main output."""
    return output_path.with_name(f"{output_path.stem}-failures.json")


def _resolve_output_format(
    *,
    explicit_format: str | None,
    config_format: str | None,
    output_path: Path,
) -> str:
    """Resolve the output format from explicit flags, config, or file extension."""
    if explicit_format is not None:
        return explicit_format
    if config_format is not None:
        return config_format
    suffix = output_path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".csv":
        return "quepid_csv"
    return "quepid_csv"


def _prepare_output_files(
    *,
    output_path: Path,
    failed_log_path: Path,
    resume: bool,
    force: bool,
) -> None:
    """Prepare output locations safely before the run starts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failed_log_path.parent.mkdir(parents=True, exist_ok=True)

    if resume:
        if not output_path.exists():
            raise click.UsageError(f"--resume was set, but {output_path} does not exist.")
        return

    if not output_path.exists():
        return

    if not force:
        confirmed = click.confirm(
            f"Output file {output_path} already exists. Overwrite it?",
            default=False,
        )
        if not confirmed:
            raise click.Abort()

    output_path.unlink()
    if failed_log_path.exists():
        failed_log_path.unlink()
