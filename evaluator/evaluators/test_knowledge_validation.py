from unittest.mock import Mock
from django.test import SimpleTestCase

from evaluator.evaluators.knowledge_validation import (
    KnowledgeValidationEvaluator,
    KnowledgeValidationLLMResult,
    PropertyCardValidationLLMResult,
)
from evaluator.extractor.schemas import Heading, Image, Link, WebsiteContent, PropertyCard


class KnowledgeValidationEvaluatorTest(SimpleTestCase):
    def create_content(self):
        return WebsiteContent(
            url="https://example.com",
            title="Bali Travel Guide",
            meta_description="Bali travel information.",
            headings=Heading(h1=["Bali Travel Guide"], h2=["Beaches"]),
            paragraphs=["Bali is an Indonesian island."],
            links=[Link(text="Hotels", href="/hotels")],
            images=[Image(src="/bali.jpg", alt="Bali Beach")],
            plain_text="Bali is an Indonesian island.",
            soup=Mock(),
            property_cards=[],
        )

    def create_llm(self, knowledge_response, card_response=None):
        llm = Mock()
        knowledge_structured = Mock()
        knowledge_structured.invoke.return_value = knowledge_response
        card_structured = Mock()
        card_structured.invoke.return_value = card_response

        def structured_output(model):
            if model is KnowledgeValidationLLMResult:
                return knowledge_structured
            if model is PropertyCardValidationLLMResult:
                return card_structured
            raise AssertionError(f"Unexpected model: {model}")

        llm.with_structured_output.side_effect = structured_output
        return llm

    def create_search(self, results=None):
        search = Mock()
        search.search.return_value = results or []
        return search

    def create_knowledge_response(
        self,
        score=100,
        verified=None,
        unsupported=None,
        uncertain=None,
        issues=None,
        recommendations=None,
    ):
        return KnowledgeValidationLLMResult(
            score=score,
            verified_claims=verified or [],
            unsupported_claims=unsupported or [],
            uncertain_claims=uncertain or [],
            issues=issues or [],
            recommendations=recommendations or [],
        )

    def test_verified_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=100,
            verified=["Bali is an Indonesian island."],
        )
        llm = self.create_llm(knowledge_response=knowledge_res)
        search = self.create_search(
            [{"title": "Bali", "url": "https://example.com", "content": "Bali is an Indonesian island."}]
        )
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.score, 100)
        self.assertEqual(result.verified_claims, ["Bali is an Indonesian island."])
        self.assertEqual(result.unsupported_claims, [])

    def test_unsupported_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=60,
            unsupported=["Bali is an Indonesian island."],
            issues=["Bali claim is unsupported by search results."],
        )
        llm = self.create_llm(knowledge_response=knowledge_res)
        search = self.create_search(
            [{"title": "Indonesia", "url": "https://example.com", "content": "Bali is part of Indonesia."}]
        )
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(self.create_content())

        self.assertIn("Bali is an Indonesian island.", result.unsupported_claims)
        self.assertTrue(any(issue.title == "Knowledge Validation" for issue in result.issues))

    def test_uncertain_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=80,
            uncertain=["Bali is an Indonesian island."],
            issues=["Insufficient evidence for claim."],
        )
        llm = self.create_llm(knowledge_response=knowledge_res)
        search = self.create_search([])
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(self.create_content())

        self.assertIn("Bali is an Indonesian island.", result.uncertain_claims)
        self.assertTrue(any(issue.title == "Knowledge Validation" for issue in result.issues))

    def test_matching_property_card(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="NYC Apartment",
                city="Jersey City",
                country="USA",
                country_code="US",
                location="Jersey City, New Jersey, USA",
                property_type="Condo",
            )
        ]

        llm = self.create_llm(
            knowledge_response=self.create_knowledge_response(),
            card_response=PropertyCardValidationLLMResult(
                status="valid",
                reason="The property is in the New York metropolitan area.",
            ),
        )

        evaluator = KnowledgeValidationEvaluator(llm=llm, search_client=self.create_search())

        result = evaluator.evaluate(content)

        self.assertFalse(any(issue.title == "Property Card Context Mismatch" for issue in result.issues))

    def test_wrong_destination_property_card(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="Luxury Paris Hotel",
                city="Paris",
                country="France",
                country_code="FR",
                location="Paris, France",
                property_type="Hotel",
            )
        ]

        llm = self.create_llm(
            knowledge_response=self.create_knowledge_response(),
            card_response=PropertyCardValidationLLMResult(
                status="context_mismatch",
                reason="The property is located in Paris, France, while the page is about New York City.",
            ),
        )

        evaluator = KnowledgeValidationEvaluator(llm=llm, search_client=self.create_search())

        result = evaluator.evaluate(content)

        self.assertTrue(any(issue.title == "Property Card Context Mismatch" for issue in result.issues))

    def test_multiple_property_cards(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="NYC Apartment",
                city="Jersey City",
                country="USA",
                country_code="US",
                location="Jersey City, New Jersey, USA",
                property_type="Condo",
            ),
            PropertyCard(
                title="Luxury Paris Hotel",
                city="Paris",
                country="France",
                country_code="FR",
                location="Paris, France",
                property_type="Hotel",
            ),
        ]

        llm = self.create_llm(
            knowledge_response=self.create_knowledge_response(),
            card_response=PropertyCardValidationLLMResult(
                status="context_mismatch",
                reason="This property belongs to Paris, France.",
            ),
        )

        evaluator = KnowledgeValidationEvaluator(llm=llm, search_client=self.create_search())

        result = evaluator.evaluate(content)

        self.assertTrue(any(issue.title == "Property Card Context Mismatch" for issue in result.issues))