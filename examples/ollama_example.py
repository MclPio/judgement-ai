"""Example usage with a local Ollama model."""

from judgement_ai import FileResultsFetcher, Grader

fetcher = FileResultsFetcher(path="results.json")
grader = Grader(
    fetcher=fetcher,
    llm_base_url="http://localhost:11434/v1",
    llm_api_key=None,
    llm_model="qwen3.5:9b",
    provider="ollama",
    response_mode="json_schema",
    think=False,
    max_retries=1,
    request_timeout=300,
)

print(grader.grade(queries=["vitamin b6"]))
