from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from judgement_ai.cli import main


def test_grade_command_uses_results_file_and_writes_json(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "judgments.json"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "1 successes" in result.output
    assert "1/1 completed" in result.stderr
    assert "Need CSV later?" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload[0]["doc_id"] == "123"


def test_grade_command_uses_config_file(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "judgments.json"
    csv_output_path = tmp_path / "judgments.csv"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: https://api.example.com/v1",
                "  api_key: ${TEST_API_KEY}",
                "  model: gpt-test",
                "search:",
                f"  results_file: {results_file}",
                "grading:",
                "  max_workers: 2",
                "  passes: 1",
                "output:",
                f"  path: {output_path}",
                f"  csv_path: {csv_output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("TEST_API_KEY", "config-key")

    def fake_post(url: str, *, headers, json, timeout):
        del json, timeout
        assert url == "https://api.example.com/v1/chat/completions"
        assert headers["Authorization"] == "Bearer config-key"

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Completed grading run" in result.output
    assert json.loads(output_path.read_text(encoding="utf-8"))[0]["doc_id"] == "123"
    assert "query,docid,rating" in csv_output_path.read_text(encoding="utf-8")


def test_grade_command_uses_safe_default_output_path_with_config(monkeypatch, tmp_path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        queries_path = Path("queries.txt")
        queries_path.write_text("vitamin b6\n", encoding="utf-8")
        results_file = Path("results.json")
        results_file.write_text(
            json.dumps(
                {
                    "vitamin b6": [
                        {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                    ]
                }
            ),
            encoding="utf-8",
        )
        config_path = Path("judgement-ai.yaml")
        config_path.write_text(
            "\n".join(
                [
                    "llm:",
                    "  api_key: test-key",
                    "  model: gpt-test",
                    "search:",
                    f"  results_file: {results_file}",
                    f"queries: {queries_path}",
                ]
            ),
            encoding="utf-8",
        )

        def fake_post(url: str, *, headers, json, timeout):
            del url, headers, json, timeout

            class DummyResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

            return DummyResponse()

        monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

        result = runner.invoke(main, ["grade", "--config", str(config_path)])

        assert result.exit_code == 0
        assert Path("judgments.json").exists()


def test_grade_command_accepts_timeout_and_retry_options(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "judgments.json"
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json
        captured["timeout"] = timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--request-timeout",
            "120",
            "--max-attempts",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["timeout"] == 120.0


def test_grade_command_uses_max_attempts_from_config(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  api_key: test-key",
                "  model: gpt-test",
                "search:",
                f"  results_file: {results_file}",
                "grading:",
                "  max_attempts: 1",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    calls = {"count": 0}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout
        calls["count"] += 1

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Missing score"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert calls["count"] == 1


def test_grade_command_accepts_temperature_option(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "judgments.json"
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        captured["temperature"] = json["temperature"]

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--temperature",
            "0.4",
        ],
    )

    assert result.exit_code == 0
    assert captured["temperature"] == 0.4


def test_grade_command_uses_structured_prompt_config(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  api_key: test-key",
                "  model: gpt-test",
                "search:",
                f"  results_file: {results_file}",
                "grading:",
                "  prompt:",
                "    instructions: |",
                "      Use the supplement catalog rubric.",
                "    output_instructions: |",
                "      Return ONLY a score line.",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        captured["prompt"] = json["messages"][0]["content"]

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Use the supplement catalog rubric." in captured["prompt"]
    assert "Return ONLY a score line." in captured["prompt"]


def test_grade_command_prompt_file_mode_uses_only_query_and_result_fields(
    monkeypatch, tmp_path
) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    prompt_file = tmp_path / "custom-prompt.txt"
    prompt_file.write_text("Query: {query}\nResult:\n{result_fields}", encoding="utf-8")
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  api_key: test-key",
                "  model: gpt-test",
                "search:",
                f"  results_file: {results_file}",
                "grading:",
                f"  prompt_file: {prompt_file}",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        captured["prompt"] = json["messages"][0]["content"]

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert captured["prompt"] == "Query: vitamin b6\nResult:\ntitle: Vitamin B6 100mg"


def test_grade_command_prompt_file_mode_rejects_hybrid_prompt_settings(tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text('{"vitamin b6": []}', encoding="utf-8")
    output_path = tmp_path / "judgments.json"
    prompt_file = tmp_path / "custom-prompt.txt"
    prompt_file.write_text("Query: {query}\nResult:\n{result_fields}", encoding="utf-8")
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  api_key: test-key",
                "  model: gpt-test",
                "search:",
                f"  results_file: {results_file}",
                "grading:",
                f"  prompt_file: {prompt_file}",
                '  domain_context: "supplements"',
                "  prompt:",
                "    instructions: |",
                "      extra instructions",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "fully self-contained" in result.output


def test_grade_command_merges_openai_compatible_options_from_config(
    monkeypatch, tmp_path
) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        '{"vitamin b6": [{"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}]}',
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: https://api.example.com/v1",
                "  api_key: test-key",
                "  model: gpt-test",
                "  provider: openai_compatible",
                "  openai_compatible:",
                "    top_p: 0.9",
                "    provider:",
                "      require_parameters: true",
                "search:",
                f"  results_file: {results_file}",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        captured["json"] = json

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert captured["json"]["top_p"] == 0.9
    assert captured["json"]["provider"]["require_parameters"] is True


def test_grade_command_ignores_openai_compatible_options_without_explicit_provider(
    monkeypatch, tmp_path
) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        '{"vitamin b6": [{"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}]}',
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: https://api.example.com/v1",
                "  api_key: test-key",
                "  model: gpt-test",
                "  openai_compatible:",
                "    top_p: 0.9",
                "search:",
                f"  results_file: {results_file}",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        captured["json"] = json

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "top_p" not in captured["json"]


def test_grade_command_merges_ollama_options_from_config(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        '{"vitamin b6": [{"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}]}',
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: http://localhost:11434/v1",
                "  api_key: null",
                "  model: qwen3.5:9b",
                "  provider: ollama",
                "  ollama:",
                '    keep_alive: "15m"',
                "    options:",
                "      top_k: 20",
                "search:",
                f"  results_file: {results_file}",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )
    captured = {}

    def fake_post(url: str, *, headers, json, timeout):
        del headers, timeout
        captured["url"] = url
        captured["json"] = json

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"message": {"content": "Direct match.\nSCORE: 3"}}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["keep_alive"] == "15m"
    assert captured["json"]["options"]["top_k"] == 20


def test_grade_command_rejects_duplicate_openai_compatible_settings(tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text('{"vitamin b6": []}', encoding="utf-8")
    output_path = tmp_path / "judgments.json"
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: https://api.example.com/v1",
                "  api_key: test-key",
                "  model: gpt-test",
                "  provider: openai_compatible",
                "  openai_compatible:",
                "    temperature: 0.9",
                "search:",
                f"  results_file: {results_file}",
                "output:",
                f"  path: {output_path}",
                f"queries: {queries_path}",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "cannot override curated settings" in result.output


def test_grade_command_uses_safe_default_output_path(monkeypatch, tmp_path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        queries_path = Path("queries.txt")
        queries_path.write_text("vitamin b6\n", encoding="utf-8")
        results_file = Path("results.json")
        results_file.write_text(
            json.dumps(
                {
                    "vitamin b6": [
                        {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                    ]
                }
            ),
            encoding="utf-8",
        )

        def fake_post(url: str, *, headers, json, timeout):
            del url, headers, json, timeout

            class DummyResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

            return DummyResponse()

        monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

        result = runner.invoke(
            main,
            [
                "grade",
                "--queries",
                str(queries_path),
                "--results-file",
                str(results_file),
                "--model",
                "gpt-test",
                "--api-key",
                "test-key",
            ],
        )

        assert result.exit_code == 0
        assert "No output path provided. Using" in result.output
        assert Path("judgments.json").exists()


def test_grade_command_uses_timestamped_default_path_on_collision(monkeypatch, tmp_path) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        queries_path = Path("queries.txt")
        queries_path.write_text("vitamin b6\n", encoding="utf-8")
        results_file = Path("results.json")
        results_file.write_text(
            json.dumps(
                {
                    "vitamin b6": [
                        {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                    ]
                }
            ),
            encoding="utf-8",
        )
        Path("judgments.json").write_text("old content", encoding="utf-8")

        def fake_post(url: str, *, headers, json, timeout):
            del url, headers, json, timeout

            class DummyResponse:
                def raise_for_status(self) -> None:
                    return None

                def json(self):
                    return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

            return DummyResponse()

        monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

        result = runner.invoke(
            main,
            [
                "grade",
                "--queries",
                str(queries_path),
                "--results-file",
                str(results_file),
                "--model",
                "gpt-test",
                "--api-key",
                "test-key",
            ],
        )

        assert result.exit_code == 0
        assert Path("judgments.json").read_text(encoding="utf-8") == "old content"
        generated = list(Path(".").glob("judgments-*.json"))
        assert len(generated) == 1


def test_grade_command_requires_input_source(tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--model",
            "gpt-test",
            "--output",
            str(tmp_path / "judgments.json"),
        ],
    )

    assert result.exit_code != 0
    assert "Provide --results-file or set search.results_file in the config file." in result.output


def test_grade_command_supports_csv_queries(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.csv"
    queries_path.write_text("query\nvitamin b6\nmagnesium\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ],
                "magnesium": [
                    {"doc_id": "456", "rank": 1, "fields": {"title": "Magnesium Glycinate"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, timeout
        query = json["messages"][0]["content"]

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                if "magnesium" in query:
                    content = "Helpful.\nSCORE: 2"
                else:
                    content = "Direct match.\nSCORE: 3"
                return {"choices": [{"message": {"content": content}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["doc_id"] for item in payload] == ["123", "456"]


def test_grade_command_requires_json_output_path(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.csv"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "Canonical raw judgments output must be a .json file." in result.output


def test_grade_command_aborts_on_existing_output_without_force(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    output_path.write_text("old content", encoding="utf-8")

    def fake_post(url: str, *, headers, json, timeout):
        raise AssertionError("provider should not be called when overwrite is declined")

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
        ],
        input="n\n",
    )

    assert result.exit_code != 0
    assert output_path.read_text(encoding="utf-8") == "old content"


def test_grade_command_force_overwrites_and_uses_sidecar_failure_log(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")

    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    output_path.write_text("old content", encoding="utf-8")
    failure_log_path = output_path.with_name("judgments-failures.json")

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Missing score line"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "Failure details were written to" in result.output
    assert failure_log_path.exists()
    payload = json.loads(failure_log_path.read_text(encoding="utf-8"))
    assert payload[0]["failure_type"] == "parse_error"


def test_grade_command_writes_optional_csv_export(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    csv_output_path = tmp_path / "judgments.csv"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Direct match.\nSCORE: 3"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Exported CSV to" in result.output
    assert "query,docid,rating" in csv_output_path.read_text(encoding="utf-8")


def test_grade_command_all_failures_still_writes_empty_json_and_csv(monkeypatch, tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(
        json.dumps(
            {
                "vitamin b6": [
                    {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
                ]
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.json"
    csv_output_path = tmp_path / "judgments.csv"
    failure_log_path = tmp_path / "judgments-failures.json"

    def fake_post(url: str, *, headers, json, timeout):
        del url, headers, json, timeout

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Missing score line"}}]}

        return DummyResponse()

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_output_path),
        ],
    )

    assert result.exit_code == 0
    assert json.loads(output_path.read_text(encoding="utf-8")) == []
    assert "query,docid,rating" in csv_output_path.read_text(encoding="utf-8")
    assert failure_log_path.exists()


def test_export_csv_command_converts_raw_json(tmp_path) -> None:
    input_path = tmp_path / "judgments.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "123",
                    "score": 3,
                    "reasoning": "Direct match.",
                    "rank": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.csv"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "export-csv",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Exported CSV to" in result.output
    assert "query,docid,rating" in output_path.read_text(encoding="utf-8")


def test_export_csv_command_aborts_on_existing_output_without_force(tmp_path) -> None:
    input_path = tmp_path / "judgments.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "query": "vitamin b6",
                    "doc_id": "123",
                    "score": 3,
                    "reasoning": "Direct match.",
                    "rank": 1,
                }
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "judgments.csv"
    output_path.write_text("old content", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "export-csv",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        input="n\n",
    )

    assert result.exit_code != 0
    assert output_path.read_text(encoding="utf-8") == "old content"


def test_grade_command_resume_requires_existing_output_after_input_validation(tmp_path) -> None:
    queries_path = tmp_path / "queries.txt"
    queries_path.write_text("vitamin b6\n", encoding="utf-8")
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps({"vitamin b6": []}), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "grade",
            "--queries",
            str(queries_path),
            "--results-file",
            str(results_file),
            "--model",
            "gpt-test",
            "--output",
            str(tmp_path / "judgments.json"),
            "--resume",
        ],
    )

    assert result.exit_code != 0
    assert "--resume was set" in result.output


def test_cli_version_option() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert "judgement-ai" in result.output


def test_preview_command_uses_placeholder_input_without_network(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: https://api.example.com/v1",
                "  api_key: secret-preview-key",
                "  model: gpt-test",
                "grading:",
                "  prompt:",
                "    instructions: |",
                "      Use the travel audio rubric.",
            ]
        ),
        encoding="utf-8",
    )

    def fail_post(*args, **kwargs):
        raise AssertionError("preview must not make network calls")

    monkeypatch.setattr("judgement_ai.grading.providers.requests.post", fail_post)

    runner = CliRunner()
    result = runner.invoke(main, ["preview", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Prompt mode: structured" in result.output
    assert "Resolved provider: openai_compatible" in result.output
    assert "Response mode: text" in result.output
    assert "Query: wireless headphones for travel" in result.output
    assert "title: Compact Noise Cancelling Headphones" in result.output
    assert (
        "description: Lightweight over-ear headphones for flights and commuting."
        in result.output
    )
    assert "Use the travel audio rubric." in result.output
    assert "secret-preview-key" not in result.output
    assert "[REDACTED]" in result.output


def test_preview_command_supports_prompt_file_mode_without_queries_or_results(tmp_path) -> None:
    prompt_file = tmp_path / "custom-prompt.txt"
    prompt_file.write_text("Query: {query}\nResult:\n{result_fields}", encoding="utf-8")
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  model: gpt-test",
                "grading:",
                f"  prompt_file: {prompt_file}",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["preview", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Prompt mode: prompt_file" in result.output
    assert "Query: wireless headphones for travel" in result.output
    assert "Result:\ntitle: Compact Noise Cancelling Headphones" in result.output


def test_preview_command_shows_ollama_json_schema_payload(tmp_path) -> None:
    config_path = tmp_path / "judgement-ai.yaml"
    config_path.write_text(
        "\n".join(
            [
                "llm:",
                "  base_url: http://localhost:11434/v1",
                "  model: qwen3.5:9b",
                "  provider: ollama",
                "  think: false",
                "  ollama:",
                '    keep_alive: "15m"',
                "    options:",
                "      top_k: 20",
                "grading:",
                "  response_mode: json_schema",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["preview", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Resolved provider: ollama" in result.output
    assert "Response mode: json_schema" in result.output
    assert '"endpoint": "http://localhost:11434/api/chat"' in result.output
    assert '"keep_alive": "15m"' in result.output
    assert '"top_k": 20' in result.output
    assert '"format": {' in result.output
