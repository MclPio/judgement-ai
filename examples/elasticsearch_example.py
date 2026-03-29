"""Example usage with Elasticsearch."""

from judgement_ai import ElasticsearchFetcher, Grader

fetcher = ElasticsearchFetcher(url="https://my-elastic/catalog", top_n=24)
grader = Grader(
    fetcher=fetcher,
    llm_base_url="https://api.openai.com/v1",
    llm_api_key="sk-...",
    llm_model="gpt-4o-mini",
)

print(grader.grade(queries=["vitamin b6"]))

