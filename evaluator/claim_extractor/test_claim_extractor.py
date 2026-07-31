from django.test import SimpleTestCase

from evaluator.claim_extractor.claim_extractor import ClaimExtractor


class ClaimExtractorTest(SimpleTestCase):

    def test_extracts_factual_claims(self):

        text = (
            "Bali is an Indonesian island. "
            "Bali has beautiful beaches. "
            "Ngurah Rai Airport is located in Denpasar."
        )

        claims = ClaimExtractor.extract(text)

        self.assertIn(
            "Bali is an Indonesian island.",
            claims,
        )

        self.assertIn(
            "Ngurah Rai Airport is located in Denpasar.",
            claims,
        )

    def test_ignores_subjective_statement(self):

        text = "Bali has beautiful beaches."

        claims = ClaimExtractor.extract(text)

        self.assertEqual(claims, [])

    def test_extracts_numeric_claim(self):

        text = "Bali received 6 million visitors in 2024."

        claims = ClaimExtractor.extract(text)

        self.assertEqual(
            claims,
            ["Bali received 6 million visitors in 2024."],
        )

    def test_extracts_multiple_claims(self):

        text = (
            "Bali is an Indonesian island. "
            "The island has several major tourist areas. "
            "Ngurah Rai Airport is located in Denpasar."
        )

        claims = ClaimExtractor.extract(text)

        self.assertEqual(len(claims), 3)

    def test_empty_text(self):

        claims = ClaimExtractor.extract("")

        self.assertEqual(claims, [])

    def test_whitespace_text(self):

        claims = ClaimExtractor.extract("   ")

        self.assertEqual(claims, [])

    def test_ignores_subjective_claim(self):

        text = (
            "Bali has amazing beaches. "
            "The island is located in Indonesia."
        )

        claims = ClaimExtractor.extract(text)

        self.assertNotIn(
            "Bali has amazing beaches.",
            claims,
        )

        self.assertIn(
            "The island is located in Indonesia.",
            claims,
        )