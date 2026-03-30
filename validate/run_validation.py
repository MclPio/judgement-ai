"""Validation entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from judgement_ai.config import load_config
from judgement_ai.fetcher import FileResultsFetcher
from judgement_ai.grader import Grader
from judgement_ai.validation import run_validation_benchmark

BENCHMARK_DATASETS = {
    "smoke": Path(__file__).with_name("datasets") / "smoke.json",
    "amazon_product_search": Path(__file__).with_name("data") / "amazon_product_search.json",
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
    parser.add_argument("--workers", type=int, help="Maximum concurrent workers.")
    parser.add_argument("--passes", type=int, help="Number of grading passes.")
    parser.add_argument("--prompt-file", type=str, help="Optional custom prompt template path.")
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

    grader = Grader(
        fetcher=FileResultsFetcher(path=BENCHMARK_DATASETS[args.benchmark]),
        llm_base_url=args.base_url or str(llm_config.get("base_url", "https://api.openai.com/v1")),
        llm_api_key=args.api_key or _string_or_none(llm_config.get("api_key")),
        llm_model=args.model or _require_string(llm_config.get("model"), "llm.model or --model"),
        domain_context=args.domain or _string_or_none(grading_config.get("domain_context")),
        max_workers=args.workers or _int_or_default(grading_config.get("max_workers"), 10),
        passes=args.passes or _int_or_default(grading_config.get("passes"), 1),
        prompt_template=args.prompt_file or _string_or_none(grading_config.get("prompt_file")),
    )

    result = run_validation_benchmark(
        benchmark=args.benchmark,
        dataset_path=BENCHMARK_DATASETS[args.benchmark],
        output_dir=args.output_dir,
        grader=grader,
    )

    summary_path = args.output_dir / f"{args.benchmark}-summary.json"
    raw_path = args.output_dir / f"{args.benchmark}-aligned.json"
    summary_path.write_text(json.dumps(result["summary"], indent=2), encoding="utf-8")
    raw_path.write_text(json.dumps(result["aligned_rows"], indent=2), encoding="utf-8")

    print(json.dumps(result["summary"], indent=2))
    if result["summary"]["status"] == "failed":
        raise SystemExit(1)


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_default(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _require_string(value: object, label: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise SystemExit(f"Provide {label}.")


if __name__ == "__main__":
    main()
