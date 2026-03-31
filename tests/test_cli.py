from __future__ import annotations

import json

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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert "1 successes" in result.output
    assert "1/1 completed" in result.stderr
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

    output_path = tmp_path / "judgments.csv"
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
                "  format: quepid_csv",
                f"  path: {output_path}",
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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

    runner = CliRunner()
    result = runner.invoke(main, ["grade", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "Completed grading run" in result.output
    assert "query,docid,rating" in output_path.read_text(encoding="utf-8")


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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
            "--output-format",
            "json",
            "--request-timeout",
            "120",
            "--max-retries",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert captured["timeout"] == 120.0


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
    assert "Provide either --elasticsearch/--results-file" in result.output


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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
            "--output-format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["doc_id"] for item in payload] == ["123", "456"]


def test_grade_command_infers_json_output_format_from_extension(monkeypatch, tmp_path) -> None:
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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
    assert payload[0]["score"] == 3


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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
            "--output-format",
            "json",
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

    monkeypatch.setattr("judgement_ai.grader.requests.post", fake_post)

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
            "--output-format",
            "json",
            "--force",
        ],
    )

    assert result.exit_code == 0
    assert "Failure details were written to" in result.output
    assert failure_log_path.exists()
    payload = json.loads(failure_log_path.read_text(encoding="utf-8"))
    assert payload[0]["failure_type"] == "parse_error"


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
