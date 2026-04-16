"""Provider-specific request and response handling."""

from __future__ import annotations

from typing import Any

import requests

from judgement_ai.grading.parsing import build_json_schema, decode_json_message
from judgement_ai.grading.types import ProviderError

OPENAI_COMPATIBLE_RESERVED_KEYS = {
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
OLLAMA_RESERVED_ROOT_KEYS = {
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
OLLAMA_RESERVED_OPTIONS_KEYS = {"temperature"}


def resolve_provider(*, llm_base_url: str, provider: str) -> str:
    """Resolve the concrete provider implementation."""
    if provider != "auto":
        return provider
    if "localhost:11434" in llm_base_url or "127.0.0.1:11434" in llm_base_url:
        return "ollama"
    return "openai_compatible"


def call_llm(
    *,
    llm_base_url: str,
    llm_api_key: str | None,
    llm_model: str,
    temperature: float,
    provider: str,
    response_mode: str,
    think: bool | None,
    request_timeout: float,
    prompt: str,
    scale_min: int,
    scale_max: int,
    openai_compatible_options: dict[str, Any] | None = None,
    ollama_options: dict[str, Any] | None = None,
) -> str | dict[str, Any]:
    """Call the configured LLM provider and return the message content."""
    resolved = resolve_provider(llm_base_url=llm_base_url, provider=provider)
    if resolved == "ollama":
        return call_ollama(
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            temperature=temperature,
            response_mode=response_mode,
            think=think,
            request_timeout=request_timeout,
            prompt=prompt,
            scale_min=scale_min,
            scale_max=scale_max,
            ollama_options=ollama_options,
        )
    return call_openai_compatible(
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        temperature=temperature,
        response_mode=response_mode,
        request_timeout=request_timeout,
        prompt=prompt,
        scale_min=scale_min,
        scale_max=scale_max,
        openai_compatible_options=openai_compatible_options,
    )


def call_openai_compatible(
    *,
    llm_base_url: str,
    llm_api_key: str | None,
    llm_model: str,
    temperature: float,
    response_mode: str,
    request_timeout: float,
    prompt: str,
    scale_min: int,
    scale_max: int,
    openai_compatible_options: dict[str, Any] | None = None,
) -> str | dict[str, Any]:
    """Call an OpenAI-compatible chat completions endpoint."""
    headers = build_openai_compatible_headers(llm_api_key=llm_api_key)
    payload = build_openai_compatible_payload(
        llm_model=llm_model,
        temperature=temperature,
        response_mode=response_mode,
        prompt=prompt,
        scale_min=scale_min,
        scale_max=scale_max,
        openai_compatible_options=openai_compatible_options,
    )

    try:
        response = requests.post(
            f"{llm_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=request_timeout,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        msg = f"LLM request timed out after {request_timeout} seconds."
        raise ProviderError(msg, failure_type="timeout") from exc
    except requests.RequestException as exc:
        msg = build_provider_error_message(exc=exc, response_mode=response_mode)
        raise ProviderError(msg, failure_type="provider_error") from exc

    data = response.json()
    message = extract_openai_message_content(data)
    if response_mode == "json_schema":
        return decode_json_message(message)
    return message


def call_ollama(
    *,
    llm_base_url: str,
    llm_model: str,
    temperature: float,
    response_mode: str,
    think: bool | None,
    request_timeout: float,
    prompt: str,
    scale_min: int,
    scale_max: int,
    ollama_options: dict[str, Any] | None = None,
) -> str | dict[str, Any]:
    """Call Ollama's native chat API for think control and structured outputs."""
    payload = build_ollama_payload(
        llm_model=llm_model,
        temperature=temperature,
        response_mode=response_mode,
        think=think,
        prompt=prompt,
        scale_min=scale_min,
        scale_max=scale_max,
        ollama_options=ollama_options,
    )

    try:
        response = requests.post(
            f"{ollama_api_root(llm_base_url)}/api/chat",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=request_timeout,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        msg = f"LLM request timed out after {request_timeout} seconds."
        raise ProviderError(msg, failure_type="timeout") from exc
    except requests.RequestException as exc:
        msg = build_provider_error_message(exc=exc, response_mode=response_mode)
        raise ProviderError(msg, failure_type="provider_error") from exc

    data = response.json()
    message = extract_ollama_message_content(data)
    if response_mode == "json_schema":
        return decode_json_message(message)
    return message


def extract_openai_message_content(data: dict[str, Any]) -> str:
    """Extract text content from an OpenAI-compatible chat completion."""
    try:
        message = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            "LLM response did not contain a chat completion message.",
            failure_type="provider_error",
        ) from exc

    if isinstance(message, str):
        return message

    if isinstance(message, list):
        text_parts = [
            part.get("text", "")
            for part in message
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        if text_parts:
            return "\n".join(text_parts)

    raise ProviderError(
        "LLM response message content was not a supported text format.",
        failure_type="provider_error",
    )


def build_openai_compatible_headers(*, llm_api_key: str | None) -> dict[str, str]:
    """Build OpenAI-compatible request headers."""
    headers = {"Content-Type": "application/json"}
    if llm_api_key:
        headers["Authorization"] = f"Bearer {llm_api_key}"
    return headers


def build_openai_compatible_payload(
    *,
    llm_model: str,
    temperature: float,
    response_mode: str,
    prompt: str,
    scale_min: int,
    scale_max: int,
    openai_compatible_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAI-compatible request payload without sending it."""
    payload: dict[str, Any] = {
        "model": llm_model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if response_mode == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "judgement_ai_grade_result",
                "strict": True,
                "schema": build_json_schema(scale_min=scale_min, scale_max=scale_max),
            },
        }
    merge_openai_compatible_options(
        payload=payload,
        extra_options=openai_compatible_options,
    )
    return payload


def extract_ollama_message_content(data: dict[str, Any]) -> str:
    """Extract text content from an Ollama chat response."""
    try:
        message = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ProviderError(
            "LLM response did not contain an Ollama chat message.",
            failure_type="provider_error",
        ) from exc
    if not isinstance(message, str):
        raise ProviderError(
            "LLM response message content was not a supported text format.",
            failure_type="provider_error",
        )
    return message


def build_ollama_payload(
    *,
    llm_model: str,
    temperature: float,
    response_mode: str,
    think: bool | None,
    prompt: str,
    scale_min: int,
    scale_max: int,
    ollama_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an Ollama chat payload without sending it."""
    payload: dict[str, Any] = {
        "model": llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if think is not None:
        payload["think"] = think
    if response_mode == "json_schema":
        payload["format"] = build_json_schema(scale_min=scale_min, scale_max=scale_max)
    merge_ollama_options(
        payload=payload,
        extra_options=ollama_options,
    )
    return payload


def build_provider_error_message(*, exc: requests.RequestException, response_mode: str) -> str:
    """Build a more actionable provider error message."""
    message = f"Failed to call LLM provider: {exc}"
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    response_text = response_text_snippet(response)
    if response_text:
        message = f"{message}. Response body: {response_text}"
    if status_code == 400 and response_mode == "json_schema":
        message = (
            f"{message}. If you are using a routed OpenAI-compatible provider, "
            "retry with text mode to confirm structured-output support."
        )
    return message


def response_text_snippet(response: Any) -> str | None:
    """Extract a short response body snippet from an HTTP error response."""
    if response is None:
        return None
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        return None
    compact = " ".join(text.split())
    if len(compact) <= 300:
        return compact
    return f"{compact[:297]}..."


def ollama_api_root(llm_base_url: str) -> str:
    """Normalize an Ollama-compatible base URL to the native API root."""
    if llm_base_url.endswith("/v1"):
        return llm_base_url[: -len("/v1")]
    return llm_base_url.rstrip("/")


def merge_openai_compatible_options(
    *,
    payload: dict[str, Any],
    extra_options: dict[str, Any] | None,
) -> None:
    """Merge advanced OpenAI-compatible payload options safely."""
    options = validate_provider_options(
        extra_options,
        label="llm.openai_compatible",
        reserved_keys=OPENAI_COMPATIBLE_RESERVED_KEYS,
    )
    payload.update(options)


def merge_ollama_options(
    *,
    payload: dict[str, Any],
    extra_options: dict[str, Any] | None,
) -> None:
    """Merge advanced Ollama payload options safely."""
    options = validate_provider_options(
        extra_options,
        label="llm.ollama",
        reserved_keys=OLLAMA_RESERVED_ROOT_KEYS,
    )
    nested_options = options.pop("options", None)
    if nested_options is not None:
        nested_mapping = validate_provider_options(
            nested_options,
            label="llm.ollama.options",
            reserved_keys=OLLAMA_RESERVED_OPTIONS_KEYS,
        )
        payload["options"].update(nested_mapping)
    payload.update(options)


def validate_provider_options(
    value: dict[str, Any] | None,
    *,
    label: str,
    reserved_keys: set[str],
) -> dict[str, Any]:
    """Validate an advanced provider passthrough mapping."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping.")
    duplicate_keys = sorted(key for key in value if key in reserved_keys)
    if duplicate_keys:
        duplicate_list = ", ".join(duplicate_keys)
        raise ValueError(
            f"{label} cannot override curated settings: {duplicate_list}."
        )
    return dict(value)
