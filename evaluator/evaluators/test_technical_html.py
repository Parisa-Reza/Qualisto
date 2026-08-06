from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from evaluator.evaluators.technical_html import TechnicalHTMLEvaluator
from evaluator.extractor.schemas import (
    Heading,
    Image,
    Link,
    WebsiteContent,
)

from unittest.mock import Mock, patch


class TechnicalHTMLEvaluatorTest(SimpleTestCase):

    def create_content(
        self,
        title="Bali Travel Guide",
        meta_description="Explore Bali.",
        h1=None,
        links=None,
        images=None,
        html=None,
    ):

        if h1 is None:
            h1 = ["Bali"]

        if links is None:
            links = [
                Link(
                    text="Home",
                    href="/",
                )
            ]

        if images is None:
            images = [
                Image(
                    src="/bali.jpg",
                    alt="Bali Beach",
                )
            ]

        if html is None:
            html = """
            <html>
                <head>
                    <title>Bali Travel Guide</title>
                </head>
                <body>

                    <h1>Bali</h1>

                    <a href="/">Home</a>

                    <img
                        src="/bali.jpg"
                        alt="Bali Beach"
                    >

                </body>
            </html>
            """

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        return WebsiteContent(
            url="https://example.com",
            title=title,
            meta_description=meta_description,
            headings=Heading(
                h1=h1,
            ),
            paragraphs=["Paragraph"],
            links=links,
            images=images,
            plain_text="Paragraph",
            soup=soup,
        )

    @patch("evaluator.evaluators.technical_html.requests.head")
    def test_valid_html(
        self,
        mock_head,
    ):

        mock_head.return_value = Mock(status_code=200)

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(),
        )

        self.assertEqual(result.score, 100)
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.recommendations), 0)

    def test_missing_title(self):

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                title="",
            ),
        )

        self.assertEqual(
            result.issues[0].title,
            "Missing HTML Title",
        )

    def test_missing_meta_description(self):

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                meta_description="",
            ),
        )

        self.assertEqual(
            result.issues[0].title,
            "Missing Meta Description",
        )

    def test_duplicate_h1(self):

        html = """
        <html>
        <head>
            <title>Bali Travel Guide</title>
        </head>
        <body>
            <h1>One</h1>
            <h1>Two</h1>
        </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(html=html)
        )

        self.assertEqual(
            result.issues[0].title,
            "Multiple H1 Tags",
        )

    def test_empty_anchor(self):

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                links=[
                    Link(
                        text="",
                        href="/about",
                    )
                ]
            ),
        )

        self.assertEqual(
            result.issues[0].title,
            "Empty Anchor Text",
        )

    def test_missing_image_alt(self):

        html = """
        <html>
        <head>
            <title>Bali Travel Guide</title>
        </head>
        <body>
            <img src="/bali.jpg">
        </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(html=html)
        )

        self.assertEqual(
            result.issues[0].title,
            "Missing Image ALT",
        )

    def test_missing_image_src(self):

        html = """
        <html>
        <head>
            <title>Bali Travel Guide</title>
        </head>
        <body>
            <img alt="Bali">
        </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(html=html)
        )

        self.assertEqual(
            result.issues[0].title,
            "Missing Image Source",
        )

    def test_invalid_heading_order(self):

        html = """
        <html>
            <head>
                <title>Bali Travel Guide</title>
            </head>
            <body>

                <h1>Main</h1>

                <h4>Skipped</h4>

            </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                html=html,
            ),
        )

        self.assertTrue(
            any(
                issue.title == "Invalid Heading Order"
                for issue in result.issues
            )
        )

    def test_duplicate_ids(self):

        html = """
        <html>
            <head>
                <title>Bali Travel Guide</title>
            </head>
            <body>

                <div id="hero"></div>

                <section id="hero"></section>

            </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                html=html,
            ),
        )

        self.assertTrue(
            any(
                issue.title == "Duplicate HTML ID"
                for issue in result.issues
            )
        )

    def test_missing_href_attribute(self):

        html = """
        <html>
            <head>
                <title>Bali Travel Guide</title>
            </head>
            <body>

                <a>About</a>

            </body>
        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                html=html,
            ),
        )

        self.assertTrue(
            any(
                issue.title == "Missing href Attribute"
                for issue in result.issues
            )
        )

    def test_multiple_issues(self):

        html = """
        <html>
            <head>
                <title>Bali Travel Guide</title>
            </head>
            <body>

                <h1>Main</h1>

                <h4>Skip</h4>

                <a></a>

                <img>

                <div id="x"></div>

                <span id="x"></span>

            </body>

        </html>
        """

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                title="",
                meta_description="",
                h1=["One", "Two"],
                html=html,
                links=[
                    Link(
                        text="",
                        href="/",
                    )
                ],
                images=[
                    Image(
                        src="",
                        alt="",
                    )
                ],
            ),
        )

        self.assertGreaterEqual(
            len(result.issues),
            8,
        )

        self.assertLess(
            result.score,
            100,
        )

    @patch("evaluator.evaluators.technical_html.requests.head")
    def test_broken_link(
        self,
        mock_head,
    ):

        mock_head.return_value = Mock(status_code=404)

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                links=[
                    Link(
                        text="Home",
                        href="/missing",
                    )
                ],
            ),
        )

        self.assertTrue(
            any(
                issue.title == "Broken Link"
                for issue in result.issues
            )
        )

    @patch("evaluator.evaluators.technical_html.requests.head")
    def test_broken_image(
        self,
        mock_head,
    ):

        mock_head.return_value = Mock(status_code=404)

        result = TechnicalHTMLEvaluator.evaluate(
            self.create_content(
                images=[
                    Image(
                        src="/missing.jpg",
                        alt="Image",
                    )
                ],
            ),
        )

        self.assertTrue(
            any(
                issue.title == "Broken Image"
                for issue in result.issues
            )
        )