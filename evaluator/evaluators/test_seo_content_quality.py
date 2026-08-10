from unittest.mock import MagicMock

from django.test import SimpleTestCase
from bs4 import BeautifulSoup

from evaluator.evaluators.seo_content_quality import (
    KeywordExtractionResult,
    SEOQualityEvaluator,
)
from evaluator.extractor.schemas import Heading, Image, Link, WebsiteContent


class SEOQualityEvaluatorTest(SimpleTestCase):

    def setUp(self):
        self.llm = MagicMock()
        self.evaluator = SEOQualityEvaluator(self.llm)

    def set_keywords(self, keywords):
        """Configure the mocked LLM to return the given keywords
        from the semantic keyword extraction step."""
        self.llm.with_structured_output.return_value.invoke.return_value = (
            KeywordExtractionResult(keywords=keywords)
        )

    def create_content(
        self,
        title="Complete Bali Travel Guide with Hotels and Beaches",
        meta_description="Discover Bali's beaches, resorts, temples, local cuisine, nightlife and travel tips for an unforgettable holiday experience with complete visitor information.",
        plain_text=None,
    ):
        html = """
        <html>
            <head>
                <title>{}</title>
            </head>
            <body>
                <h1>Bali Travel Guide</h1>
                <h2>Hotels</h2>

                <a href="/hotels">Hotels</a>

                <img
                    src="/bali.jpg"
                    alt="Bali Beach"
                >

                <p>
                    Bali is one of the world's most popular tourist destinations.
                </p>
            </body>
        </html>
        """.format(title)

        soup = BeautifulSoup(html, "html.parser")
        if plain_text is None:
            sentence = (
                "Bali is one of the world's most popular tourist destinations, "
                "offering beautiful beaches, temples, local culture, and outdoor activities."
            )
            paragraphs = [sentence] * 50
            plain_text = " ".join(paragraphs)
        else:
            paragraphs = [plain_text]

        return WebsiteContent(
            url="https://example.com",
            title=title,
            meta_description=meta_description,
            headings=Heading(h1=["Bali Travel Guide"], h2=["Hotels"]),
            links=[Link(text="Hotels", href="/hotels")],
            images=[Image(src="/bali.jpg", alt="Bali Beach")],
            paragraphs=paragraphs,
            plain_text=plain_text,
            soup=soup,
        )


    def test_valid_title(self):
        result = self.evaluator.evaluate(self.create_content())
        self.assertEqual(result.score, 100)
        self.assertEqual(len(result.issues), 0)
        self.assertEqual(len(result.recommendations), 0)

    def test_missing_title(self):
        result = self.evaluator.evaluate(self.create_content(title=""))
        self.assertEqual(result.issues[0].title, "Missing SEO Title")
        self.assertEqual(result.recommendations[0].title, "Add SEO Title")

    def test_title_too_short(self):
        result = self.evaluator.evaluate(self.create_content(title="Bali Guide"))
        self.assertEqual(result.issues[0].title, "Title Too Short")

    def test_title_too_long(self):
        result = self.evaluator.evaluate(
            self.create_content(
                title=(
                    "The Ultimate Complete Detailed Comprehensive "
                    "Bali Travel Guide Covering Every Attraction "
                    "You Should Visit During Your Vacation"
                ),
            ),
        )
        self.assertEqual(result.issues[0].title, "Title Too Long")



    def test_valid_meta_description(self):
        result = self.evaluator.evaluate(self.create_content())
        self.assertFalse(
            any(issue.title == "Missing Meta Description" for issue in result.issues)
        )

    def test_missing_meta_description(self):
        result = self.evaluator.evaluate(self.create_content(meta_description=""))
        self.assertEqual(result.issues[0].title, "Missing Meta Description")

    def test_meta_description_too_short(self):
        result = self.evaluator.evaluate(
            self.create_content(meta_description="Visit Bali.")
        )
        self.assertTrue(
            any(issue.title == "Meta Description Too Short" for issue in result.issues)
        )

    def test_meta_description_too_long(self):
        description = (
            "Bali is one of the most beautiful tourist destinations in the world offering "
            "beaches, temples, mountains, nightlife, luxury resorts, local culture, shopping, "
            "food experiences, adventure sports, wellness retreats and many unforgettable experiences "
            "for every type of traveller throughout the year."
        )
        result = self.evaluator.evaluate(
            self.create_content(meta_description=description)
        )
        self.assertTrue(
            any(issue.title == "Meta Description Too Long" for issue in result.issues)
        )



    def test_thin_content(self):
        result = self.evaluator.evaluate(
            self.create_content(plain_text=" ".join(["bali"] * 120)),
        )
        self.assertTrue(any(issue.title == "Thin Content" for issue in result.issues))

    def test_low_content_coverage(self):
        result = self.evaluator.evaluate(
            self.create_content(plain_text=" ".join(["bali"] * 500)),
        )
        self.assertTrue(
            any(issue.title == "Low Content Coverage" for issue in result.issues)
        )

    def test_good_content_length(self):
        result = self.evaluator.evaluate(
            self.create_content(plain_text=" ".join(["bali"] * 1000)),
        )
        self.assertFalse(
            any(
                issue.title in (
                    "Thin Content",
                    "Low Content Coverage",
                    "Very Long Content",
                    "Excessively Long Content",
                )
                for issue in result.issues
            )
        )

    def test_very_long_content(self):
        result = self.evaluator.evaluate(
            self.create_content(plain_text=" ".join(["bali"] * 3000)),
        )
        self.assertTrue(
            any(issue.title == "Very Long Content" for issue in result.issues)
        )

    def test_excessively_long_content(self):
        result = self.evaluator.evaluate(
            self.create_content(plain_text=" ".join(["bali"] * 4500)),
        )
        self.assertTrue(
            any(issue.title == "Excessively Long Content" for issue in result.issues)
        )


    def test_long_paragraphs(self):
        paragraph = " ".join(["bali"] * 200)
        result = self.evaluator.evaluate(self.create_content(plain_text=paragraph))
        self.assertTrue(
            any(issue.title == "Long Paragraphs" for issue in result.issues)
        )

    def test_low_internal_linking(self):
        content = self.create_content(plain_text=" ".join(["bali"] * 1200))
        content.links = []
        result = self.evaluator.evaluate(content)
        self.assertTrue(
            any(issue.title == "Low Internal Linking" for issue in result.issues)
        )

    def test_too_many_external_links(self):
        content = self.create_content()
        content.links = [
            Link(text=f"Link {i}", href=f"https://example{i}.com")
            for i in range(30)
        ]
        result = self.evaluator.evaluate(content)
        self.assertTrue(
            any(issue.title == "Too Many External Links" for issue in result.issues)
        )

    def test_low_image_coverage(self):
        content = self.create_content(plain_text=" ".join(["bali"] * 1800))
        content.images = []
        result = self.evaluator.evaluate(content)
        self.assertTrue(
            any(issue.title == "Low Image Coverage" for issue in result.issues)
        )


    def test_duplicate_headings(self):
        content = self.create_content()
        content.headings = Heading(h1=["Bali"], h2=["Hotels", "Hotels"])
        result = self.evaluator.evaluate(content)
        self.assertTrue(
            any(issue.title == "Duplicate Headings" for issue in result.issues)
        )

    def test_generic_headings(self):
        content = self.create_content()
        content.headings = Heading(h1=["Home"], h2=["Section"])
        result = self.evaluator.evaluate(content)
        self.assertTrue(
            any(issue.title == "Generic Headings" for issue in result.issues)
        )

    def test_low_readability(self):
        sentence = " ".join(["bali"] * 200) + "."
        result = self.evaluator.evaluate(self.create_content(plain_text=sentence))
        self.assertTrue(
            any(issue.title == "Low Readability" for issue in result.issues)
        )


    def test_extract_keywords_from_user_prompt(self):
        self.set_keywords(["Bali", "Bali beaches", "Bali hotels"])

        keywords = self.evaluator._extract_keywords(
            "Create a travel webpage about Bali beaches and Bali hotels."
        )

        self.assertIn("bali", keywords)
        self.assertIn("bali beaches", keywords)
        self.assertIn("bali hotels", keywords)

    def test_missing_target_topic(self):
        self.set_keywords(["london"])

        content = self.create_content(
            plain_text=(
                "Bali is beautiful. "
                "Bali has beaches and temples. "
                + " ".join(["destination"] * 300)
            ),
        )
        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about London.",
        )
        self.assertTrue(
            any(issue.title == "Missing Target Topics" for issue in result.issues)
        )

    def test_keyword_present_in_body(self):
        self.set_keywords(["bali"])

        content = self.create_content(
            plain_text=(
                "Bali is a popular travel destination "
                "with beaches and temples."
            ),
        )
        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about Bali.",
        )
        self.assertFalse(
            any(issue.title == "Missing Target Topics" for issue in result.issues)
        )

    def test_keyword_only_in_body_has_weak_placement(self):
        self.set_keywords(["bali"])

        content = self.create_content(
            plain_text="Bali is a popular travel destination.",
        )
        content.title = "Complete Travel Guide"
        content.meta_description = "A complete travel guide."
        content.headings = Heading(h1=["Travel Guide"], h2=["Hotels"], h3=[])

        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about Bali.",
        )
        self.assertTrue(
            any(issue.title == "Weak Keyword Placement" for issue in result.issues)
        )

    def test_keyword_density_is_case_insensitive(self):
        self.set_keywords(["bali"])

        content = self.create_content(
            plain_text=(
                "Bali is beautiful. "
                "bali has beaches. "
                "BALI has temples. "
                "Bali has culture and food. "
                + " ".join(["destination"] * 300)
            ),
        )
        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about Bali.",
        )
        # 4 occurrences / ~315 words ≈ 1.27%.
        # Must NOT be considered high density (>2%).
        self.assertFalse(
            any(issue.title == "Potential Keyword Overuse" for issue in result.issues)
        )

    def test_high_keyword_density(self):
        self.set_keywords(["bali"])

        content = self.create_content(
            plain_text=(
                " ".join(["bali"] * 30)
                + " "
                + " ".join(["destination"] * 100)
            ),
        )
        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about Bali.",
        )
        self.assertTrue(
            any(issue.title == "Potential Keyword Overuse" for issue in result.issues)
        )

    def test_low_keyword_density(self):
        self.set_keywords(["bali"])

        content = self.create_content(
            plain_text=(
                "Bali is a beautiful destination "
                "with beaches and temples. "
                + " ".join(["destination"] * 500)
            ),
        )
        result = self.evaluator.evaluate(
            content,
            user_prompt="Create a travel webpage about Bali.",
        )
        self.assertTrue(
            any(
                issue.title == "Low Target Keyword Coverage"
                for issue in result.issues
            )
        )

    def test_empty_prompt_skips_keyword_checks(self):
        content = self.create_content()
        result = self.evaluator.evaluate(content, user_prompt="")
        self.assertFalse(
            any(
                issue.title in (
                    "Missing Target Topics",
                    "Weak Keyword Placement",
                    "Low Target Keyword Coverage",
                    "Potential Keyword Overuse",
                )
                for issue in result.issues
            )
        )