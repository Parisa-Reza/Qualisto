from django.test import SimpleTestCase

from evaluator.extractor.schemas import (
    Heading,
    Image,
    Link,
    WebsiteContent,
)


class TestSchemas(SimpleTestCase):

    def test_heading_schema(self):
        heading = Heading(
            h1=["Welcome"],
            h2=["About"],
        )

        self.assertEqual(heading.h1, ["Welcome"])
        self.assertEqual(heading.h2, ["About"])
        self.assertEqual(heading.h3, [])
        self.assertEqual(heading.h4, [])
        self.assertEqual(heading.h5, [])
        self.assertEqual(heading.h6, [])

    def test_link_schema(self):
        link = Link(
            text="Home",
            href="https://example.com",
        )

        self.assertEqual(link.text, "Home")
        self.assertEqual(link.href, "https://example.com")

    def test_image_schema(self):
        image = Image(
            src="/images/banner.jpg",
            alt="Banner",
        )

        self.assertEqual(image.src, "/images/banner.jpg")
        self.assertEqual(image.alt, "Banner")

    def test_website_content_schema(self):

        heading = Heading(
            h1=["Example"],
            h2=["Section"],
            
        )

        links = [
            Link(
                text="Home",
                href="https://example.com",
            )
        ]

        images = [
            Image(
                src="/banner.jpg",
                alt="Banner",
            )
        ]

        content = WebsiteContent(
            url="https://example.com",
            title="Example",
            meta_description="Example description",
            headings=heading,
            paragraphs=["Paragraph 1"],
            links=links,
            images=images,
            plain_text="Paragraph 1",
        )

        self.assertEqual(content.url, "https://example.com")
        self.assertEqual(content.title, "Example")
        self.assertEqual(content.meta_description, "Example description")

        self.assertEqual(content.headings.h1, ["Example"])
        self.assertEqual(content.headings.h2, ["Section"])
        self.assertEqual(content.headings.h3, [])
        self.assertEqual(content.headings.h4, [])
        self.assertEqual(content.headings.h5, [])
        self.assertEqual(content.headings.h6, [])

        self.assertEqual(len(content.paragraphs), 1)
        self.assertEqual(content.paragraphs[0], "Paragraph 1")

        self.assertEqual(len(content.links), 1)
        self.assertEqual(content.links[0].text, "Home")
        self.assertEqual(content.links[0].href, "https://example.com")

        self.assertEqual(len(content.images), 1)
        self.assertEqual(content.images[0].src, "/banner.jpg")
        self.assertEqual(content.images[0].alt, "Banner")

        self.assertEqual(content.plain_text, "Paragraph 1")