"""Example usage with pre-fetched results."""

from judgement_ai import FileResultsFetcher, Grader

fetcher = FileResultsFetcher(path="results.json")
grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="sk-...",
    llm_model="gpt-4o-mini",
)

print(grader.grade(queries=["vitamin b6", "tired all the time"]))

