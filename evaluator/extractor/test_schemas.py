import unittest

from evaluator.extractor.schemas import (
    Heading,
    Image,
    Link,
    WebsiteContent,
)


class TestSchemas(unittest.TestCase):

    def test_heading(self):
        heading = Heading(
            h1=["Welcome"],
            h2=["About"]
        )

        self.assertEqual(heading.h1, ["Welcome"])
        self.assertEqual(heading.h2, ["About"])

    def test_link(self):
        link = Link(
            text="Home",
            href="https://example.com"
        )

        self.assertEqual(link.text, "Home")
        self.assertEqual(link.href, "https://example.com")

    def test_image(self):
        image = Image(
            src="/images/banner.jpg",
            alt="Banner"
        )

        self.assertEqual(image.src, "/images/banner.jpg")
        self.assertEqual(image.alt, "Banner")

    def test_website_content(self):

        content = WebsiteContent(
            url="https://example.com",
            title="Example",
            meta_description="Example description",
            headings=Heading(
                h1=["Example"],
                h2=["Section"]
            ),
            paragraphs=["Paragraph 1"],
            links=[
                Link(
                    text="Home",
                    href="https://example.com"
                )
            ],
            images=[
                Image(
                    src="/banner.jpg",
                    alt="Banner"
                )
            ],
            plain_text="Paragraph 1"
        )

        self.assertEqual(content.url, "https://example.com")
        self.assertEqual(content.title, "Example")
        self.assertEqual(content.meta_description, "Example description")
        self.assertEqual(len(content.links), 1)
        self.assertEqual(len(content.images), 1)
        self.assertEqual(content.headings.h1[0], "Example")