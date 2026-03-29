from judgement_ai.prompts import DEFAULT_PROMPT_TEMPLATE, validate_prompt_template


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

