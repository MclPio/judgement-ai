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


def config_mapping(config: dict[str, Any], key: str, *, label: str) -> dict[str, Any] | None:
    value = config.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise click.UsageError(f"{label} must be a mapping.")
    return value


def has_config_value(config: dict[str, Any], key: str) -> bool:
    if key not in config:
        return False
    value = config.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict | list):
        return bool(value)
    return True


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
    max_attempts: int | None,
    provider: str | None,
    response_mode: str | None,
    think: bool | None,
    prompt_file: Path | None,
) -> Grader:
    """Build the grader from CLI arguments and config."""
    grader_kwargs = resolve_grader_kwargs(
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
    return Grader(fetcher=fetcher, **grader_kwargs)


def resolve_grader_kwargs(
    *,
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
    max_attempts: int | None,
    provider: str | None,
    response_mode: str | None,
    think: bool | None,
    prompt_file: Path | None,
) -> dict[str, Any]:
    """Resolve grader settings from CLI arguments and config."""
    llm_model = model_name or config_str(llm_config, "model")
    if not llm_model:
        raise click.UsageError("Provide --model or set llm.model in the config file.")

    prompt_settings = resolve_prompt_settings(
        grading_config=grading_config,
        domain_context=domain_context,
        prompt_file=prompt_file,
    )
    effective_provider = provider or config_str(llm_config, "provider") or "auto"
    openai_compatible_options, ollama_options = resolve_provider_options(
        llm_config=llm_config,
        effective_provider=effective_provider,
    )

    return {
        "llm_base_url": (
            base_url or config_str(llm_config, "base_url") or "https://api.openai.com/v1"
        ),
        "llm_api_key": api_key if api_key is not None else config_str(llm_config, "api_key"),
        "llm_model": llm_model,
        "domain_context": prompt_settings["domain_context"],
        "scale_min": prompt_settings["scale_min"],
        "scale_max": prompt_settings["scale_max"],
        "scale_labels": prompt_settings["scale_labels"],
        "max_workers": max_workers or config_int(grading_config, "max_workers") or 10,
        "passes": passes or config_int(grading_config, "passes") or 1,
        "temperature": (
            temperature
            if temperature is not None
            else config_float(grading_config, "temperature") or 0.0
        ),
        "max_attempts": max_attempts or config_int(grading_config, "max_attempts") or 1,
        "request_timeout": (
            request_timeout
            if request_timeout is not None
            else config_float(grading_config, "request_timeout") or 60.0
        ),
        "provider": effective_provider,
        "response_mode": response_mode or config_str(grading_config, "response_mode") or "text",
        "think": think if think is not None else config_bool(llm_config, "think"),
        "prompt_template": prompt_settings["prompt_template"],
        "prompt_contract": prompt_settings["prompt_contract"],
        "prompt_instructions": prompt_settings["prompt_instructions"],
        "output_instructions": prompt_settings["output_instructions"],
        "openai_compatible_options": openai_compatible_options,
        "ollama_options": ollama_options,
    }


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
    output_path.write_text("[]", encoding="utf-8")
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


def resolve_prompt_settings(
    *,
    grading_config: dict[str, Any],
    domain_context: str | None,
    prompt_file: Path | None,
) -> dict[str, Any]:
    """Resolve prompt-related settings and enforce mode exclusivity."""
    prompt_config = config_mapping(
        grading_config,
        "prompt",
        label="grading.prompt",
    ) or {}
    unexpected_prompt_keys = sorted(
        key for key in prompt_config if key not in {"instructions", "output_instructions"}
    )
    if unexpected_prompt_keys:
        unexpected_list = ", ".join(unexpected_prompt_keys)
        raise click.UsageError(
            f"grading.prompt only supports instructions and output_instructions, got: "
            f"{unexpected_list}."
        )

    effective_prompt_file = resolve_prompt_file_path(
        prompt_file=prompt_file,
        grading_config=grading_config,
    )
    if effective_prompt_file is not None:
        conflicts = []
        if domain_context is not None:
            conflicts.append("--domain")
        for key in ("scale_min", "scale_max", "scale_labels", "domain_context"):
            if has_config_value(grading_config, key):
                conflicts.append(f"grading.{key}")
        for key in ("instructions", "output_instructions"):
            if has_config_value(prompt_config, key):
                conflicts.append(f"grading.prompt.{key}")
        if conflicts:
            raise click.UsageError(
                "Custom prompt-file mode is fully self-contained. Remove these "
                f"prompt-related settings: {', '.join(conflicts)}."
            )
        return {
            "prompt_template": str(effective_prompt_file),
            "prompt_contract": "prompt_file",
            "prompt_instructions": None,
            "output_instructions": None,
            "domain_context": None,
            "scale_min": 0,
            "scale_max": 3,
            "scale_labels": None,
        }

    scale_min = config_int(grading_config, "scale_min")
    scale_max = config_int(grading_config, "scale_max")
    scale_labels = grading_config.get("scale_labels")
    return {
        "prompt_template": None,
        "prompt_contract": "structured",
        "prompt_instructions": config_str(prompt_config, "instructions"),
        "output_instructions": config_str(prompt_config, "output_instructions"),
        "domain_context": (
            domain_context
            if domain_context is not None
            else config_str(grading_config, "domain_context")
        ),
        "scale_min": scale_min if scale_min is not None else 0,
        "scale_max": scale_max if scale_max is not None else 3,
        "scale_labels": scale_labels if isinstance(scale_labels, dict) else None,
    }


def resolve_prompt_file_path(
    *,
    prompt_file: Path | None,
    grading_config: dict[str, Any],
) -> Path | None:
    """Resolve the effective custom prompt file path, if configured."""
    if prompt_file is not None:
        return prompt_file
    configured_prompt_file = config_str(grading_config, "prompt_file")
    if configured_prompt_file is None:
        return None
    resolved = Path(configured_prompt_file)
    if not resolved.exists():
        raise click.UsageError(
            "grading.prompt_file must point to an existing file."
        )
    return resolved


def resolve_provider_options(
    *,
    llm_config: dict[str, Any],
    effective_provider: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve advanced provider passthrough blocks from config."""
    configured_provider = config_str(llm_config, "provider")
    openai_compatible_options = (
        config_mapping(
            llm_config,
            "openai_compatible",
            label="llm.openai_compatible",
        )
        if configured_provider == effective_provider == "openai_compatible"
        else None
    )
    ollama_options = (
        config_mapping(llm_config, "ollama", label="llm.ollama")
        if configured_provider == effective_provider == "ollama"
        else None
    )
    validate_openai_compatible_options(openai_compatible_options)
    validate_ollama_options(ollama_options)
    return openai_compatible_options or {}, ollama_options or {}


def validate_openai_compatible_options(
    options: dict[str, Any] | None,
) -> None:
    """Reject advanced OpenAI-compatible config that overlaps curated fields."""
    if options is None:
        return
    duplicate_keys = sorted(
        key
        for key in options
        if key
        in {
            "api_key",
            "base_url",
            "messages",
            "model",
            "request_timeout",
            "response_format",
            "response_mode",
            "temperature",
            "think",
        }
    )
    if duplicate_keys:
        raise click.UsageError(
            "llm.openai_compatible cannot override curated settings: "
            f"{', '.join(duplicate_keys)}."
        )


def validate_ollama_options(options: dict[str, Any] | None) -> None:
    """Reject advanced Ollama config that overlaps curated fields."""
    if options is None:
        return
    duplicate_root_keys = sorted(
        key
        for key in options
        if key
        in {
            "api_key",
            "base_url",
            "format",
            "messages",
            "model",
            "request_timeout",
            "response_mode",
            "stream",
            "temperature",
            "think",
        }
    )
    if duplicate_root_keys:
        raise click.UsageError(
            "llm.ollama cannot override curated settings: "
            f"{', '.join(duplicate_root_keys)}."
        )
    nested_options = options.get("options")
    if nested_options is None:
        return
    if not isinstance(nested_options, dict):
        raise click.UsageError("llm.ollama.options must be a mapping.")
    duplicate_option_keys = sorted(
        key for key in nested_options if key in {"temperature"}
    )
    if duplicate_option_keys:
        raise click.UsageError(
            "llm.ollama.options cannot override curated settings: "
            f"{', '.join(duplicate_option_keys)}."
        )
