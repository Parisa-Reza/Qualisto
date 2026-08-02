import os

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()


class TavilySearchClient:

    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")

        if not api_key:
            raise ValueError("TAVILY_API_KEY is not configured.")

        self.client = TavilyClient(api_key=api_key)

    def search(self, query: str, max_results: int = 5) -> list[dict]:

        query = query.strip()

        if not query:
            return []

        # Tavily accepts queries of at most 400 characters. Claims extracted
        # from page content can be longer, so keep the request within its API
        # limit instead of failing the entire evaluation.
        query = query[:400]

        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
        )

        return response.get("results", [])
