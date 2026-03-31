"""Example usage with pre-fetched results."""

from judgement_ai import FileResultsFetcher, Grader

# results.json shape:
# {
#   "vitamin b6": [
#     {"doc_id": "123", "rank": 1, "fields": {"title": "Vitamin B6 100mg"}}
#   ]
# }
#
fetcher = FileResultsFetcher(path="results.json")
grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
    response_mode="json_schema",
)

print(grader.grade(queries=["vitamin b6", "tired all the time"]))
