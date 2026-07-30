from django.test import SimpleTestCase
from bs4 import BeautifulSoup

from evaluator.extractor.parser import HTMLParser


class HTMLParserTest(SimpleTestCase):

    def test_parse_valid_html(self):

        html = """
        <html>
            <head>
                <title>Example</title>
            </head>

            <body>

                <h1>Hello World</h1>

            </body>

        </html>
        """

        soup = HTMLParser.parse(html)

        self.assertIsInstance(soup, BeautifulSoup)
        self.assertEqual(soup.title.string, "Example")
        self.assertEqual(soup.h1.string, "Hello World")

    def test_empty_html(self):

        with self.assertRaises(ValueError):
            HTMLParser.parse("")

    def test_none_html(self):

        with self.assertRaises(ValueError):
            HTMLParser.parse(None)