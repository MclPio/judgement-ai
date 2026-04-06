"""Validation entrypoint."""
# ruff: noqa: I001

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judgement_ai.config import load_config
from judgement_ai.fetcher import FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.progress import TerminalProgressReporter
from judgement_ai.validation import run_validation_benchmark

BENCHMARK_DATASETS = {
    "smoke": Path(__file__).with_name("datasets") / "smoke.json",
    "amazon_product_search": Path(__file__).with_name("data") / "amazon_product_search.json",
    "amazon_product_search_calibration": (
        Path(__file__).with_name("data") / "amazon_product_search_calibration.json"
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run validation benchmarks for judgement-ai.")
    parser.add_argument(
        "--benchmark",
        choices=sorted(BENCHMARK_DATASETS),
        default="smoke",
        help="Benchmark id to run.",
    )
    parser.add_argument("--config", type=Path, help="Optional YAML config file.")
    parser.add_argument("--model", type=str, help="LLM model name.")
    parser.add_argument("--base-url", type=str, help="OpenAI-compatible base URL.")
    parser.add_argument("--api-key", type=str, help="API key for the LLM provider.")
    parser.add_argument("--domain", type=str, help="Optional domain context for grading.")
    parser.add_argument(
        "--provider",
        choices=["auto", "ollama", "openai_compatible"],
        help="LLM provider mode.",
    )
    parser.add_argument("--workers", type=int, help="Maximum concurrent workers.")
    parser.add_argument("--passes", type=int, help="Number of grading passes.")
    parser.add_argument("--temperature", type=float, help="Sampling temperature for the LLM.")
    parser.add_argument(
        "--request-timeout",
        type=float,
        help="Provider request timeout in seconds.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        help="Attempts per item during this run. Use 1 for a mostly single-pass run.",
    )
    parser.add_argument(
        "--response-mode",
        choices=["json_schema", "text"],
        help="LLM output mode. Validation defaults to json_schema.",
    )
    parser.add_argument(
        "--prompt-profile",
        choices=["default", "amazon_esci"],
        help="Named prompt profile to use for validation.",
    )
    parser.add_argument("--prompt-file", type=str, help="Optional custom prompt template path.")
    parser.add_argument(
        "--think",
        dest="think",
        action="store_true",
        default=None,
        help="Enable provider thinking when supported.",
    )
    parser.add_argument(
        "--no-think",
        dest="think",
        action="store_false",
        help="Disable provider thinking when supported.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing raw judgments in the output directory.",
    )
    parser.add_argument(
        "--retry-failures",
        type=Path,
        help="Rerun only failed rows from a prior failures artifact.",
    )
    parser.add_argument(
        "--skip-calibration-gates",
        action="store_true",
        help="Run the full Amazon benchmark even if calibration gate files are missing or failing.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("artifacts"),
        help="Directory for benchmark artifacts.",
    )
    args = parser.parse_args()

    config = load_config(args.config) if args.config else {}
    llm_config = config.get("llm", {}) if isinstance(config.get("llm"), dict) else {}
    grading_config = (
        config.get("grading", {}) if isinstance(config.get("grading"), dict) else {}
    )


    scale_labels = grading_config.get("scale_labels")
    resolved_scale_labels = scale_labels
    resolved_prompt_template = (
        args.prompt_file
        or _string_or_none(grading_config.get("prompt_file"))
    )
    if args.benchmark == "amazon_product_search" and not args.skip_calibration_gates:
        _require_calibration_gates(args.output_dir)

    grader = Grader(
        fetcher=FileResultsFetcher(path=BENCHMARK_DATASETS[args.benchmark]),
        llm_base_url=args.base_url or str(llm_config.get("base_url", "https://api.openai.com/v1")),
        llm_api_key=args.api_key or _string_or_none(llm_config.get("api_key")),
        llm_model=args.model or _require_string(llm_config.get("model"), "llm.model or --model"),
        domain_context=args.domain or _string_or_none(grading_config.get("domain_context")),
        max_workers=args.workers or _int_or_default(grading_config.get("max_workers"), 10),
        passes=args.passes or _int_or_default(grading_config.get("passes"), 1),
        temperature=args.temperature
        if args.temperature is not None
        else _float_or_default(grading_config.get("temperature"), 0.0),
        max_retries=args.max_retries
        if args.max_retries is not None
        else _int_or_default(grading_config.get("max_retries"), 1),
        request_timeout=args.request_timeout
        if args.request_timeout is not None
        else _float_or_default(grading_config.get("request_timeout"), 60.0),
        prompt_template=resolved_prompt_template,
        scale_labels=resolved_scale_labels,
        provider=args.provider
        or _string_or_none(llm_config.get("provider"))
        or "auto",
        response_mode=args.response_mode
        or _string_or_none(grading_config.get("response_mode"))
        or "json_schema",
        think=args.think if args.think is not None else _bool_or_none(llm_config.get("think")),
    )
    reporter = TerminalProgressReporter(label=f"validation:{args.benchmark}")

    result = run_validation_benchmark(
        benchmark=args.benchmark,
        dataset_path=BENCHMARK_DATASETS[args.benchmark],
        output_dir=args.output_dir,
        grader=grader,
        resume=args.resume,
        retry_failures_from=args.retry_failures,
        progress_callback=reporter,
    )

    print(json.dumps(result["summary"], indent=2))
    print(
        "Completed validation run: "
        f"{result['summary']['benchmark']} | "
        f"rows={result['summary']['metrics']['num_rows']} | "
        f"scored={result['summary']['metrics']['num_scored_rows']} | "
        f"failed={result['summary']['metrics']['num_failed_rows']}",
        file=sys.stderr,
    )
    if result["summary"]["status"] == "failed":
        raise SystemExit(1)


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_default(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _float_or_default(value: object, default: float) -> float:
    return float(value) if isinstance(value, int | float) else default


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _require_string(value: object, label: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise SystemExit(f"Provide {label}.")


def _require_calibration_gates(output_dir: Path) -> None:
    """Require a passing reference calibration gate before the full run."""
    reference_gate = _find_gate(output_dir, "amazon_product_search_calibration-reference-gate.json")
    if reference_gate is None:
        raise SystemExit(
            "Full amazon_product_search runs are blocked until a reference calibration gate "
            "exists and passes. Run amazon_product_search_calibration with a strong "
            "reference model first, or use --skip-calibration-gates to bypass this."
        )

    if not _gate_passed(reference_gate):
        details = _gate_failure_message(reference_gate)
        raise SystemExit(f"Reference calibration failed: {details}")


def _find_gate(output_dir: Path, filename: str) -> Path | None:
    """Find a gate file in the output directory or nearby artifact roots."""
    roots = [output_dir]
    if output_dir.parent != output_dir:
        roots.append(output_dir.parent)

    seen: set[Path] = set()
    for root in roots:
        if root in seen or not root.exists():
            continue
        seen.add(root)
        direct = root / filename
        if direct.exists():
            return direct
        for candidate in root.rglob(filename):
            return candidate
    return None


def _gate_passed(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(payload.get("passed"))


def _gate_failure_message(path: Path) -> str:
    """Summarize why a gate file failed."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    failed_reasons = payload.get("failed_reasons", [])
    metrics = payload.get("metrics", {})
    parts: list[str] = []
    for reason in failed_reasons:
        if reason == "spearman_at_least_0_40":
            parts.append(f"spearman {metrics.get('spearman')} < 0.40")
        elif reason == "no_parse_failures":
            count = (
                payload.get("analysis", {})
                .get("failure_counts_by_type", {})
                .get("parse_error", 0)
            )
            parts.append(f"{count} parse failures")
        elif reason == "no_timeout_failures":
            count = payload.get("analysis", {}).get("failure_counts_by_type", {}).get("timeout", 0)
            parts.append(f"{count} timeout failures")
        elif reason == "no_score_collapse":
            parts.append("score collapse warning")
        elif reason == "uses_at_least_three_labels":
            parts.append("fewer than three labels used")
        elif reason == "failure_rate_at_most_5_percent":
            parts.append("failure rate exceeded 5%")
        else:
            parts.append(str(reason))
    return ", ".join(parts) if parts else "unknown gate failure"


if __name__ == "__main__":
    main()
