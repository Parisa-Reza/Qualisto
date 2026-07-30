from django.test import SimpleTestCase

from evaluator.extractor.content_extractor import ContentExtractor
from evaluator.extractor.parser import HTMLParser


class ContentExtractorTest(SimpleTestCase):

    def setUp(self):

        self.url = "https://example.com"

        self.html = """
        <html>

            <head>

                <title>Bali Travel Guide</title>

                <meta
                    name="description"
                    content="Explore Bali beaches and culture.">

            </head>

            <body>

                <h1>Bali</h1>

                <h2>Beaches</h2>

                <h2>Food</h2>

                <p>Paragraph One.</p>

                <p>Paragraph Two.</p>

                <a href="/about">
                    About Us
                </a>

                <img
                    src="/bali.jpg"
                    alt="Bali Beach">

            </body>

        </html>
        """

        self.soup = HTMLParser.parse(self.html)

    def test_extract_title(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            content.title,
            "Bali Travel Guide",
        )

    def test_extract_meta_description(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            content.meta_description,
            "Explore Bali beaches and culture.",
        )

    def test_extract_h1(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            content.headings.h1,
            ["Bali"],
        )

    def test_extract_h2(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            len(content.headings.h2),
            2,
        )

    def test_extract_paragraphs(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            len(content.paragraphs),
            2,
        )

    def test_extract_links(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            len(content.links),
            1,
        )

        self.assertEqual(
            content.links[0].href,
            "/about",
        )

    def test_extract_images(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            len(content.images),
            1,
        )

        self.assertEqual(
            content.images[0].alt,
            "Bali Beach",
        )

    def test_extract_plain_text(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertIn(
            "Paragraph One.",
            content.plain_text,
        )

    def test_extract_complete_object(self):

        content = ContentExtractor.extract(
            self.url,
            self.soup,
        )

        self.assertEqual(
            content.url,
            self.url,
        )

        self.assertEqual(
            content.title,
            "Bali Travel Guide",
        )

        self.assertEqual(
            len(content.paragraphs),
            2,
        )

        self.assertEqual(
            len(content.links),
            1,
        )

        self.assertEqual(
            len(content.images),
            1,
        )