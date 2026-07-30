import requests

from django.test import SimpleTestCase

from evaluator.extractor.fetcher import HTMLFetcher


class HTMLFetcherTest(SimpleTestCase):

    def test_fetch_valid_url(self):

        html = HTMLFetcher.fetch(
            "https://example.com"
        )

        self.assertIsInstance(html, str)
        self.assertGreater(len(html), 0)
        self.assertIn("<html", html.lower())

    def test_invalid_domain(self):

        with self.assertRaises(requests.RequestException):
            HTMLFetcher.fetch(
                "https://this-domain-does-not-exist-123456.com"
            )

    def test_invalid_url(self):

        with self.assertRaises(requests.RequestException):
            HTMLFetcher.fetch(
                "invalid-url"
            )