from unittest.mock import Mock

from django.test import SimpleTestCase

from evaluator.evaluators.knowledge_validation import (
    DestinationResolutionLLMResult,
    KnowledgeValidationEvaluator,
    KnowledgeValidationLLMResult,
    PropertyCardValidationLLMResult,
)
from evaluator.evaluators.schemas import KnowledgeValidationResult
from evaluator.extractor.schemas import (
    Heading,
    Image,
    Link,
    PropertyCard,
    WebsiteContent,
)


class KnowledgeValidationEvaluatorTest(SimpleTestCase):
    def create_content(self):
        return WebsiteContent(
            url="https://example.com",
            title="Bali Travel Guide",
            meta_description="Bali travel information.",
            headings=Heading(
                h1=["Bali Travel Guide"],
                h2=["Beaches"],
                h3=[],
                h4=[],
                h5=[],
                h6=[],
            ),
            paragraphs=["Bali is an Indonesian island."],
            links=[Link(text="Hotels", href="/hotels")],
            images=[Image(src="/bali.jpg", alt="Bali Beach")],
            plain_text="Bali is an Indonesian island.",
            soup=Mock(),
            property_cards=[],
        )

    def create_llm(self, knowledge_response, destination_response=None, card_responses=None):
        llm = Mock()
        knowledge_structured = Mock()
        destination_structured = Mock()
        card_structured = Mock()
        knowledge_structured.invoke.return_value = knowledge_response
        destination_structured.invoke.return_value = destination_response
        card_responses = card_responses or {}
        card_structured.invoke.side_effect = lambda prompt: card_responses.get(
            self._extract_card_title(prompt),
            PropertyCardValidationLLMResult(
                status="valid",
                reason="No mismatch detected.",
            ),
        )

        def structured_output(model):
            if model is KnowledgeValidationLLMResult:
                return knowledge_structured
            if model is DestinationResolutionLLMResult:
                return destination_structured
            if model is PropertyCardValidationLLMResult:
                return card_structured
            raise AssertionError(f"Unexpected model: {model}")

        llm.with_structured_output.side_effect = structured_output
        return llm

    @staticmethod
    def _extract_card_title(prompt):
        marker = "Title:"
        if marker not in prompt:
            return ""
        value = prompt.split(marker, 1)[1].split("\n", 1)[0]
        return value.strip()

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

    def create_destination_response(
        self,
        destination="Bali",
        country="Indonesia",
        country_code="ID",
    ):
        return DestinationResolutionLLMResult(
            destination=destination,
            country=country,
            country_code=country_code,
            explanation="The requested destination is Bali, Indonesia.",
        )

    def test_verified_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=100,
            verified=["Bali is an Indonesian island."],
        )
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        search = self.create_search(
            [
                {
                    "title": "Bali",
                    "url": "https://example.com",
                    "content": "Bali is an Indonesian island.",
                }
            ]
        )
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(
            content=self.create_content(),
            user_prompt="Create a travel guide for Bali.",
        )
        self.assertEqual(result.score, 100)
        self.assertEqual(
            result.verified_claims,
            ["Bali is an Indonesian island."],
        )
        self.assertEqual(result.unsupported_claims, [])

    def test_unsupported_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=60,
            unsupported=["Bali is an Indonesian island."],
            issues=["Bali claim is unsupported by search results."],
        )
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        search = self.create_search(
            [
                {
                    "title": "Indonesia",
                    "url": "https://example.com",
                    "content": "Bali is part of Indonesia.",
                }
            ]
        )
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(
            content=self.create_content(),
            user_prompt="Create a travel guide for Bali.",
        )
        self.assertIn(
            "Bali is an Indonesian island.",
            result.unsupported_claims,
        )
        self.assertTrue(
            any(
                issue.title == "Knowledge Validation"
                for issue in result.issues
            )
        )

    def test_uncertain_claim(self):
        knowledge_res = self.create_knowledge_response(
            score=80,
            uncertain=["Bali is an Indonesian island."],
            issues=["Insufficient evidence for claim."],
        )
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        search = self.create_search([])
        evaluator = KnowledgeValidationEvaluator(llm, search)
        result = evaluator.evaluate(
            content=self.create_content(),
            user_prompt="Create a travel guide for Bali.",
        )
        self.assertIn(
            "Bali is an Indonesian island.",
            result.uncertain_claims,
        )
        self.assertTrue(
            any(
                issue.title == "Knowledge Validation"
                for issue in result.issues
            )
        )

    def test_matching_property_card(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="Bali Beach Resort",
                city="Bali",
                country="Indonesia",
                country_code="ID",
                location="Bali, Indonesia",
                property_type="Resort",
            )
        ]
        knowledge_res = self.create_knowledge_response()
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        evaluator = KnowledgeValidationEvaluator(
            llm=llm,
            search_client=self.create_search(),
        )
        result = evaluator.evaluate(
            content=content,
            user_prompt="Create a travel guide for Bali.",
        )
        self.assertFalse(
            any(
                issue.title == "Property Card Context Mismatch"
                for issue in result.issues
            )
        )
        self.assertEqual(result.score, 100)

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
        knowledge_res = self.create_knowledge_response()
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        evaluator = KnowledgeValidationEvaluator(
            llm=llm,
            search_client=self.create_search(),
        )
        result = evaluator.evaluate(
            content=content,
            user_prompt="Create a travel guide for Bali.",
        )
        self.assertTrue(
            any(
                issue.title == "Property Card Context Mismatch"
                for issue in result.issues
            )
        )
        self.assertEqual(result.score, 0)

    def test_multiple_property_cards(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="Bali Beach Resort",
                city="Bali",
                country="Indonesia",
                country_code="ID",
                location="Bali, Indonesia",
                property_type="Resort",
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
        knowledge_res = self.create_knowledge_response()
        destination_res = self.create_destination_response()
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
        )
        evaluator = KnowledgeValidationEvaluator(
            llm=llm,
            search_client=self.create_search(),
        )
        result = evaluator.evaluate(
            content=content,
            user_prompt="Create a travel guide for Bali.",
        )
        mismatches = [
            issue
            for issue in result.issues
            if issue.title == "Property Card Context Mismatch"
        ]
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(result.score, 50)

    def test_same_country_ambiguous_property_card_valid(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="New York Hotel",
                city="New York",
                country="United States",
                country_code="US",
                location="New York, United States",
                property_type="Hotel",
            )
        ]
        knowledge_res = self.create_knowledge_response()
        destination_res = DestinationResolutionLLMResult(
            destination="New York",
            country="United States",
            country_code="US",
            explanation="The requested destination is New York.",
        )
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
            card_responses={
                "New York Hotel": PropertyCardValidationLLMResult(
                    status="valid",
                    reason="The property belongs to New York.",
                )
            },
        )
        evaluator = KnowledgeValidationEvaluator(
            llm=llm,
            search_client=self.create_search(
                [
                    {
                        "title": "New York Hotel",
                        "url": "https://example.com",
                        "content": "Hotel located in New York, United States.",
                    }
                ]
            ),
        )
        result = evaluator.evaluate(
            content=content,
            user_prompt="Create a travel guide for New York.",
        )
        self.assertFalse(
            any(
                issue.title == "Property Card Context Mismatch"
                for issue in result.issues
            )
        )
        self.assertEqual(result.score, 100)

    def test_same_country_ambiguous_property_card_invalid(self):
        content = self.create_content()
        content.property_cards = [
            PropertyCard(
                title="New Jersey Hotel",
                city="New Jersey",
                country="United States",
                country_code="US",
                location="New Jersey, United States",
                property_type="Hotel",
            )
        ]
        knowledge_res = self.create_knowledge_response()
        destination_res = DestinationResolutionLLMResult(
            destination="New York",
            country="United States",
            country_code="US",
            explanation="The requested destination is New York.",
        )
        llm = self.create_llm(
            knowledge_response=knowledge_res,
            destination_response=destination_res,
            card_responses={
                "New Jersey Hotel": PropertyCardValidationLLMResult(
                    status="context_mismatch",
                    reason="The property is located in New Jersey, not New York.",
                )
            },
        )
        evaluator = KnowledgeValidationEvaluator(
            llm=llm,
            search_client=self.create_search(
                [
                    {
                        "title": "New Jersey Hotel",
                        "url": "https://example.com",
                        "content": "Hotel located in New Jersey, United States.",
                    }
                ]
            ),
        )
        result = evaluator.evaluate(
            content=content,
            user_prompt="Create a travel guide for New York.",
        )
        self.assertTrue(
            any(
                issue.title == "Property Card Context Mismatch"
                for issue in result.issues
            )
        )
        self.assertEqual(result.score, 0)