"""Preview the resolved prompt and request payload without grading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from judgement_ai.cli.common import config_section, resolve_grader_kwargs
from judgement_ai.config import load_config
from judgement_ai.grading.providers import (
    build_ollama_payload,
    build_openai_compatible_headers,
    build_openai_compatible_payload,
    ollama_api_root,
    resolve_provider,
)
from judgement_ai.prompts import build_prompt, load_prompt_template

PLACEHOLDER_QUERY = "wireless headphones for travel"
PLACEHOLDER_RESULT_FIELDS = {
    "title": "Compact Noise Cancelling Headphones",
    "description": "Lightweight over-ear headphones for flights and commuting.",
}


@click.command()
@click.option(
    "--config",
    "config_path_value",
    type=click.Path(exists=True, path_type=Path),
    help="Optional YAML config file.",
)
@click.option("--model", "model_name", type=str, help="LLM model name.")
@click.option("--base-url", type=str, help="OpenAI-compatible base URL.")
@click.option("--api-key", default=None, help="LLM provider API key.")
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
def preview(
    config_path_value: Path | None,
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
) -> None:
    """Preview the resolved prompt and outgoing request payload."""
    config = load_config(config_path_value) if config_path_value else {}
    llm_config = config_section(config, "llm")
    grading_config = config_section(config, "grading")
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

    rendered_prompt = build_prompt(
        query=PLACEHOLDER_QUERY,
        result_fields=PLACEHOLDER_RESULT_FIELDS,
        scale_labels=grader_kwargs["scale_labels"],
        domain_context=grader_kwargs["domain_context"],
        prompt_template=load_prompt_template(grader_kwargs["prompt_template"]),
        prompt_instructions=grader_kwargs["prompt_instructions"],
        output_instructions=grader_kwargs["output_instructions"],
        response_mode=grader_kwargs["response_mode"],
        prompt_contract=grader_kwargs["prompt_contract"],
    )
    resolved_provider = resolve_provider(
        llm_base_url=grader_kwargs["llm_base_url"],
        provider=grader_kwargs["provider"],
    )
    request_preview = build_request_preview(
        grader_kwargs=grader_kwargs,
        prompt=rendered_prompt,
        resolved_provider=resolved_provider,
    )
    redacted = redact_sensitive_preview(
        {
            "prompt": rendered_prompt,
            "request": request_preview,
        },
        secrets=collect_preview_secrets(grader_kwargs=grader_kwargs),
    )

    click.echo(f"Prompt mode: {grader_kwargs['prompt_contract']}")
    click.echo(f"Resolved provider: {resolved_provider}")
    click.echo(f"Response mode: {grader_kwargs['response_mode']}")
    click.echo()
    click.echo("Rendered prompt:")
    click.echo(redacted["prompt"])
    click.echo()
    click.echo("Request payload shape:")
    click.echo(json.dumps(redacted["request"], indent=2, sort_keys=True))


def build_request_preview(
    *,
    grader_kwargs: dict[str, Any],
    prompt: str,
    resolved_provider: str,
) -> dict[str, Any]:
    """Build the outgoing request artifact without sending it."""
    if resolved_provider == "ollama":
        return {
            "endpoint": f"{ollama_api_root(grader_kwargs['llm_base_url'])}/api/chat",
            "headers": {"Content-Type": "application/json"},
            "json": build_ollama_payload(
                llm_model=grader_kwargs["llm_model"],
                temperature=grader_kwargs["temperature"],
                response_mode=grader_kwargs["response_mode"],
                think=grader_kwargs["think"],
                prompt=prompt,
                scale_min=grader_kwargs["scale_min"],
                scale_max=grader_kwargs["scale_max"],
                ollama_options=grader_kwargs["ollama_options"],
            ),
        }
    return {
        "endpoint": f"{grader_kwargs['llm_base_url'].rstrip('/')}/chat/completions",
        "headers": build_openai_compatible_headers(
            llm_api_key=grader_kwargs["llm_api_key"]
        ),
        "json": build_openai_compatible_payload(
            llm_model=grader_kwargs["llm_model"],
            temperature=grader_kwargs["temperature"],
            response_mode=grader_kwargs["response_mode"],
            prompt=prompt,
            scale_min=grader_kwargs["scale_min"],
            scale_max=grader_kwargs["scale_max"],
            openai_compatible_options=grader_kwargs["openai_compatible_options"],
        ),
    }


def collect_preview_secrets(*, grader_kwargs: dict[str, Any]) -> set[str]:
    """Collect exact secret values to redact from preview output."""
    secrets = set()
    api_key = grader_kwargs.get("llm_api_key")
    if isinstance(api_key, str) and api_key.strip():
        secrets.add(api_key)
        secrets.add(f"Bearer {api_key}")
    return secrets


def redact_sensitive_preview(value: Any, *, secrets: set[str]) -> Any:
    """Recursively redact exact secret string matches from preview output."""
    if isinstance(value, dict):
        return {
            key: redact_sensitive_preview(item, secrets=secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_preview(item, secrets=secrets) for item in value]
    if isinstance(value, str):
        redacted = value
        for secret in sorted(secrets, key=len, reverse=True):
            redacted = redacted.replace(secret, "[REDACTED]")
        return redacted
    return value
