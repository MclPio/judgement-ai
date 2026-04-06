from judgement_ai.prompts import (
    DEFAULT_PROMPT_TEMPLATE,
    DEFAULT_SCALE_LABELS,
    build_prompt,
    render_domain_context,
    render_output_instructions,
    render_result_fields,
    render_scale_labels,
    validate_prompt_template,
    validate_scale_labels,
)


def test_default_prompt_has_required_fields() -> None:
    validate_prompt_template(DEFAULT_PROMPT_TEMPLATE)


def test_validate_prompt_template_rejects_missing_required_fields() -> None:
    broken_template = "Query: {query}\nScale: {scale_labels}"

    try:
        validate_prompt_template(broken_template)
    except ValueError as exc:
        assert "result_fields" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing placeholder")


def test_validate_scale_labels_requires_complete_range() -> None:
    try:
        validate_scale_labels(
            scale_min=0,
            scale_max=3,
            scale_labels={0: "Irrelevant", 1: "Related", 3: "Perfect"},
        )
    except ValueError as exc:
        assert "missing labels" in str(exc)
    else:
        raise AssertionError("Expected ValueError for incomplete scale labels")


def test_render_scale_labels_is_sorted() -> None:
    rendered = render_scale_labels({2: "Relevant", 0: "Irrelevant", 1: "Related"})

    assert rendered == "0: Irrelevant\n1: Related\n2: Relevant"


def test_render_domain_context_is_optional() -> None:
    assert render_domain_context(None) == ""
    assert render_domain_context("  Nutritional supplements catalog  ").startswith(
        "Domain context:\nNutritional supplements catalog"
    )


def test_render_result_fields_supports_dicts() -> None:
    rendered = render_result_fields({"title": "Vitamin B6", "description": "Energy support"})

    assert "title: Vitamin B6" in rendered
    assert "description: Energy support" in rendered


def test_build_prompt_includes_domain_context_scale_and_query() -> None:
    prompt = build_prompt(
        query="vitamin b6",
        result_fields={"title": "Vitamin B6 100mg", "brand": "Acme"},
        scale_labels=DEFAULT_SCALE_LABELS,
        domain_context="This is a catalog of nutritional supplements and vitamins.",
    )

    assert "Query: vitamin b6" in prompt
    assert "Domain context:" in prompt
    assert "0: Completely irrelevant" in prompt
    assert "title: Vitamin B6 100mg" in prompt


def test_build_prompt_uses_json_schema_output_instructions() -> None:
    prompt = build_prompt(
        query="wireless headphones",
        result_fields={"title": "Headphones"},
        response_mode="json_schema",
    )

    assert "Respond with a JSON object" in prompt
    assert "SCORE: <number>" not in prompt


def test_render_output_instructions_rejects_unknown_mode() -> None:
    try:
        render_output_instructions("unknown")
    except ValueError as exc:
        assert "Unsupported response_mode" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported response mode")
