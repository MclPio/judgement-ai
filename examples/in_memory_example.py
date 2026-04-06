"""Example usage with in-memory results."""

from judgement_ai import Grader, InMemoryResultsFetcher

fetcher = InMemoryResultsFetcher(
    {
        "vitamin b6": [
            {
                "doc_id": "123",
                "fields": {
                    "title": "Vitamin B6 100mg",
                    "description": "Supports energy metabolism",
                },
            },
            {
                "doc_id": "456",
                "fields": {
                    "title": "B Complex",
                    "description": "Balanced vitamin B formulation",
                },
            },
        ]
    }
)

grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
    response_mode="json_schema",
)

print(grader.grade(queries=["vitamin b6"]))
