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

        if not query.strip():
            return []

        response = self.client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=False,
        )

        return response.get("results", [])