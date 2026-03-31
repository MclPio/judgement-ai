"""Example usage with Elasticsearch."""

from judgement_ai import ElasticsearchFetcher, Grader

fetcher = ElasticsearchFetcher(url="https://my-elastic/catalog", top_n=24)
grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="YOUR_API_KEY",
    llm_model="gpt-5.1",
    response_mode="json_schema",
)

print(grader.grade(queries=["vitamin b6"]))
