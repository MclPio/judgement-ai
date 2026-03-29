"""Example usage with Ollama-compatible endpoint."""

from judgement_ai import FileResultsFetcher, Grader

fetcher = FileResultsFetcher(path="results.json")
grader = Grader(
    fetcher=fetcher,
    llm_base_url="http://localhost:11434/v1",
    llm_api_key=None,
    llm_model="llama3",
)

print(grader.grade(queries=["vitamin b6"]))

