"""Shared CLI helpers."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from judgement_ai.fetcher import FileResultsFetcher
from judgement_ai.grading import Grader


def load_queries(path: Path) -> list[str]:
    """Load queries from a text file or CSV file."""
    if path.suffix.lower() == ".csv":
        return load_queries_from_csv(path)
    return load_queries_from_text(path)


def load_queries_from_text(path: Path) -> list[str]:
    """Load one query per line from a text file."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_queries_from_csv(path: Path) -> list[str]:
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


def build_fetcher(*, results_file: Path | None) -> FileResultsFetcher:
    """Build the configured fetcher implementation."""
    if results_file is None:
        raise click.UsageError(
            "Provide --results-file or set search.results_file in the config file."
        )
    return FileResultsFetcher(path=results_file)


def config_section(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key, {})
    return value if isinstance(value, dict) else {}


def config_str(config: dict[str, Any], key: str) -> str | None:
    value = config.get(key)
    return value if isinstance(value, str) else None


def config_int(config: dict[str, Any], key: str) -> int | None:
    value = config.get(key)
    return value if isinstance(value, int) else None


def config_path(config: dict[str, Any], key: str) -> Path | None:
    value = config_str(config, key)
    return Path(value) if value else None


def config_float(config: dict[str, Any], key: str) -> float | None:
    value = config.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def config_bool(config: dict[str, Any], key: str) -> bool | None:
    value = config.get(key)
    return value if isinstance(value, bool) else None


def resolve_output_path(
    *,
    output_path: Path | None,
    output_config: dict[str, Any],
    resume: bool,
) -> tuple[Path, bool]:
    """Resolve an explicit or safe default canonical output path."""
    resolved = output_path or config_path(output_config, "path")
    if resolved is not None:
        return resolved, False
    return default_output_path(cwd=Path.cwd(), resume=resume), True


def default_output_path(*, cwd: Path, resume: bool) -> Path:
    """Return a safe default raw judgments path in the current directory."""
    base_path = cwd / "judgments.json"
    if resume or not base_path.exists():
        return base_path
    return timestamped_variant(base_path)


def timestamped_variant(path: Path) -> Path:
    """Return a unique timestamped sibling path derived from the provided base path."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(f"{path.stem}-{timestamp}{path.suffix}")
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{timestamp}-{counter}{path.suffix}")
        counter += 1
    return candidate


def validate_raw_output_path(output_path: Path) -> None:
    """Ensure the canonical output path is a JSON file."""
    if output_path.suffix.lower() != ".json":
        raise click.UsageError(
            "Canonical raw judgments output must be a .json file. "
            "Use --csv-output for optional CSV export."
        )


def validate_csv_output_path(output_path: Path) -> None:
    """Ensure the export output path is a CSV file."""
    if output_path.suffix.lower() != ".csv":
        raise click.UsageError("CSV export output must be a .csv file.")


def build_grader(
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
    llm_model = model_name or config_str(llm_config, "model")
    if not llm_model:
        raise click.UsageError("Provide --model or set llm.model in the config file.")

    scale_min = config_int(grading_config, "scale_min")
    scale_max = config_int(grading_config, "scale_max")
    scale_labels = grading_config.get("scale_labels")

    return Grader(
        fetcher=fetcher,
        llm_base_url=base_url or config_str(llm_config, "base_url") or "https://api.openai.com/v1",
        llm_api_key=api_key if api_key is not None else config_str(llm_config, "api_key"),
        llm_model=llm_model,
        domain_context=domain_context
        if domain_context is not None
        else config_str(grading_config, "domain_context"),
        scale_min=scale_min if scale_min is not None else 0,
        scale_max=scale_max if scale_max is not None else 3,
        scale_labels=scale_labels if isinstance(scale_labels, dict) else None,
        max_workers=max_workers or config_int(grading_config, "max_workers") or 10,
        passes=passes or config_int(grading_config, "passes") or 1,
        temperature=temperature
        if temperature is not None
        else config_float(grading_config, "temperature")
        or 0.0,
        max_retries=max_retries
        if max_retries is not None
        else config_int(grading_config, "max_retries")
        or 3,
        request_timeout=request_timeout
        if request_timeout is not None
        else config_float(grading_config, "request_timeout")
        or 60.0,
        provider=provider or config_str(llm_config, "provider") or "auto",
        response_mode=response_mode or config_str(grading_config, "response_mode") or "text",
        think=think if think is not None else config_bool(llm_config, "think"),
        prompt_template=str(prompt_file)
        if prompt_file is not None
        else config_str(grading_config, "prompt_file"),
    )


def default_failure_log_path(output_path: Path) -> Path:
    """Return the default failure log path beside the main output."""
    return output_path.with_name(f"{output_path.stem}-failures.json")


def prepare_output_files(
    *,
    output_path: Path,
    failed_log_path: Path,
    csv_output_path: Path | None,
    resume: bool,
    force: bool,
) -> None:
    """Prepare output locations safely before the run starts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failed_log_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_output_path is not None:
        csv_output_path.parent.mkdir(parents=True, exist_ok=True)

    if resume:
        if not output_path.exists():
            raise click.UsageError(f"--resume was set, but {output_path} does not exist.")
        return

    prepare_single_output_file(path=output_path, force=force)
    if failed_log_path.exists():
        failed_log_path.unlink()
    if csv_output_path is not None:
        prepare_single_output_file(path=csv_output_path, force=force)


def prepare_single_output_file(*, path: Path, force: bool) -> None:
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
