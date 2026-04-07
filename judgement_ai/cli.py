"""Thin Click CLI over the library."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from judgement_ai import __version__
from judgement_ai.config import load_config
from judgement_ai.fetcher import FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.output import write_quepid_csv
from judgement_ai.progress import TerminalProgressReporter
from judgement_ai.results_io import load_json_results


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="judgement-ai")
def main() -> None:
    """Entry point for the judgement-ai CLI."""


@main.command("export-quepid")
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
    help="Quepid CSV output path.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing output files without prompting.",
)
def export_quepid(
    input_path: Path,
    output_path: Path,
    force: bool,
) -> None:
    """Export canonical raw judgments JSON as Quepid CSV."""
    _validate_raw_output_path(input_path)
    _validate_csv_output_path(output_path)
    results = load_json_results(input_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _prepare_single_output_file(path=output_path, force=force)
    write_quepid_csv(results, output_path)

    click.echo(f"Loaded canonical raw judgments from {input_path}.")
    click.echo(f"Exported Quepid CSV to {output_path}.")
    click.echo(f"Wrote {len(results)} rows.")


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
    "--quepid-output",
    "quepid_output_path",
    type=click.Path(path_type=Path),
    help="Optional Quepid CSV export path derived from the canonical JSON output.",
)
@click.option("--domain", "domain_context", type=str, help="Optional domain context.")
@click.option("--workers", "max_workers", type=int, help="Maximum concurrent workers.")
@click.option("--passes", type=int, help="Number of grading passes per item.")
@click.option("--temperature", type=float, help="Sampling temperature for the LLM.")
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
    results_file: Path | None,
    model_name: str | None,
    base_url: str | None,
    api_key: str | None,
    output_path: Path | None,
    quepid_output_path: Path | None,
    domain_context: str | None,
    max_workers: int | None,
    passes: int | None,
    temperature: float | None,
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
        results_file=results_file or _config_path(search_config, "results_file"),
    )

    final_output_path, output_path_was_defaulted = _resolve_output_path(
        output_path=output_path,
        output_config=output_config,
        resume=resume,
    )
    _validate_raw_output_path(final_output_path)
    final_quepid_output_path = quepid_output_path or _config_path(output_config, "quepid_path")
    failed_log_path = _default_failure_log_path(final_output_path)
    _prepare_output_files(
        output_path=final_output_path,
        failed_log_path=failed_log_path,
        quepid_output_path=final_quepid_output_path,
        resume=resume,
        force=force,
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
        temperature=temperature,
        request_timeout=request_timeout,
        max_retries=max_retries,
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

    if final_quepid_output_path is not None:
        all_results = load_json_results(final_output_path)
        write_quepid_csv(all_results, final_quepid_output_path)

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
    if final_quepid_output_path is not None:
        click.echo(f"Exported Quepid CSV to {final_quepid_output_path}.")
    else:
        suggested_export_path = final_output_path.with_suffix(".csv")
        click.echo(
            "Need Quepid CSV later? "
            "Run `judgement-ai export-quepid "
            f"--input {final_output_path} --output {suggested_export_path}`."
        )
    click.echo(f"Wrote {len(results)} new results in this run.")
    if summary["failures"] > 0:
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
    results_file: Path | None,
):
    """Build the configured fetcher implementation."""
    if results_file is None:
        raise click.UsageError(
            "Provide --results-file or set search.results_file in the config file."
        )
    return FileResultsFetcher(path=results_file)


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


def _resolve_output_path(
    *,
    output_path: Path | None,
    output_config: dict[str, Any],
    resume: bool,
) -> tuple[Path, bool]:
    """Resolve an explicit or safe default canonical output path."""
    resolved = output_path or _config_path(output_config, "path")
    if resolved is not None:
        return resolved, False
    return _default_output_path(cwd=Path.cwd(), resume=resume), True


def _default_output_path(*, cwd: Path, resume: bool) -> Path:
    """Return a safe default raw judgments path in the current directory."""
    base_path = cwd / "judgments.json"
    if resume or not base_path.exists():
        return base_path
    return _timestamped_variant(base_path)


def _timestamped_variant(path: Path) -> Path:
    """Return a unique timestamped sibling path derived from the provided base path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}-{timestamp}{path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{timestamp}-{counter}{path.suffix}")
        counter += 1
    return candidate


def _validate_raw_output_path(output_path: Path) -> None:
    """Ensure the canonical output path is a JSON file."""
    if output_path.suffix.lower() != ".json":
        raise click.UsageError(
            "Canonical raw judgments output must be a .json file. "
            "Use --quepid-output for optional CSV export."
        )


def _validate_csv_output_path(output_path: Path) -> None:
    """Ensure the export output path is a CSV file."""
    if output_path.suffix.lower() != ".csv":
        raise click.UsageError("Quepid export output must be a .csv file.")


def _build_grader(
    *,
    fetcher: FileResultsFetcher,
    llm_config: dict[str, Any],
    grading_config: dict[str, Any],
    model_name: str | None,
    base_url: str | None,
    api_key: str | None,
    domain_context: str | None,
    max_workers: int | None,
    passes: int | None,
    temperature: float | None,
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
        temperature=temperature
        if temperature is not None
        else _config_float(grading_config, "temperature")
        or 0.0,
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


def _prepare_output_files(
    *,
    output_path: Path,
    failed_log_path: Path,
    quepid_output_path: Path | None,
    resume: bool,
    force: bool,
) -> None:
    """Prepare output locations safely before the run starts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failed_log_path.parent.mkdir(parents=True, exist_ok=True)
    if quepid_output_path is not None:
        quepid_output_path.parent.mkdir(parents=True, exist_ok=True)

    if resume:
        if not output_path.exists():
            raise click.UsageError(f"--resume was set, but {output_path} does not exist.")
        return

    _prepare_single_output_file(path=output_path, force=force)
    if failed_log_path.exists():
        failed_log_path.unlink()
    if quepid_output_path is not None:
        _prepare_single_output_file(path=quepid_output_path, force=force)


def _prepare_single_output_file(*, path: Path, force: bool) -> None:
    """Prepare one output file path before a non-resume run."""
    if not path.exists():
        return

    if not force:
        confirmed = click.confirm(
            f"Output file {path} already exists. Overwrite it?",
            default=False,
        )
        if not confirmed:
            raise click.Abort()

    path.unlink()
