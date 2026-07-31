from unittest.mock import patch

from django.test import SimpleTestCase

from evaluator.tavily_search.tavily import TavilySearchClient


class TavilySearchClientTest(SimpleTestCase):

    @patch("evaluator.tavily_search.tavily.TavilyClient")
    def test_search_returns_results(self, mock_client):

        mock_client.return_value.search.return_value = {
            "results": [
                {
                    "title": "Eiffel Tower",
                    "url": "https://example.com/eiffel",
                    "content": "The Eiffel Tower is located in Paris.",
                }
            ]
        }

        client = TavilySearchClient()

        results = client.search(
            "Where is the Eiffel Tower located?"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["title"],
            "Eiffel Tower",
        )

    @patch("evaluator.tavily_search.tavily.TavilyClient")
    def test_search_uses_max_results(self, mock_client):

        mock_client.return_value.search.return_value = {
            "results": []
        }

        client = TavilySearchClient()

        client.search(
            "Bali tourist attractions",
            max_results=3,
        )

        mock_client.return_value.search.assert_called_once_with(
            query="Bali tourist attractions",
            search_depth="advanced",
            max_results=3,
            include_answer=False,
        )

    @patch("evaluator.tavily_search.tavily.TavilyClient")
    def test_empty_query_returns_empty_list(self, mock_client):

        client = TavilySearchClient()

        results = client.search("   ")

        self.assertEqual(results, [])

        mock_client.return_value.search.assert_not_called()

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key(self):

        with self.assertRaises(ValueError):
            TavilySearchClient()