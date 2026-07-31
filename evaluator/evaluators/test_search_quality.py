from unittest.mock import Mock
from django.test import SimpleTestCase
from evaluator.evaluators.search_quality import SearchQualityEvaluator, SearchQualityLLMResult
from evaluator.extractor.schemas import Heading, Image, Link, WebsiteContent


class SearchQualityEvaluatorTest(SimpleTestCase):
    def create_content(self):
        return WebsiteContent(
            url="https://example.com/bali",
            title="Bali Travel Guide",
            meta_description=("Complete travel guide to Bali."),
            headings=Heading(h1=["Bali Travel Guide"], h2=["Best Places to Visit", "Things to Do", "Where to Stay"]),
            paragraphs=[("Bali is a popular travel destination with beaches, temples, and cultural attractions.")],
            links=[Link(text="Hotels", href="/hotels")],
            images=[Image(src="/bali.jpg", alt="Bali beach")],
            plain_text=("Bali is a popular travel destination with beaches, temples, and cultural attractions."),
            soup=Mock(),
            property_cards=[],
        )

    def create_llm(self, response):
        llm = Mock()
        structured = Mock()
        structured.invoke.return_value = response
        llm.with_structured_output.return_value = (structured)
        return llm

    def create_response(self, score=90):
        return SearchQualityLLMResult(
            score=score,
            # FIX:
            # search_intent is text, not a numeric score.
            search_intent=("Informational travel planning for Bali."),
            helpfulness_score=90,
            completeness_score=88,
            natural_writing_score=94,
            repetition_score=95,
            ai_sounding_score=90,
            content_depth_score=85,
            missing_sections=["Transportation"],
            readability_score=93,
            user_satisfaction_score=91,
            issues=["Transportation information is missing."],
            recommendations=["Add a transportation section."],
        )

    def test_evaluate_returns_search_quality_result(self):
        llm = self.create_llm(self.create_response())
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.score, 90)
        # FIX:
        # Check search_intent instead of search_intent_score.
        self.assertEqual(result.search_intent, "Informational travel planning for Bali.")
        self.assertEqual(result.helpfulness_score, 90)
        self.assertEqual(result.completeness_score, 88)
        self.assertEqual(result.content_depth_score, 85)
        self.assertEqual(result.readability_score, 93)
        self.assertEqual(result.user_satisfaction_score, 91)

    def test_missing_sections_are_preserved(self):
        llm = self.create_llm(self.create_response())
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.missing_sections, ["Transportation"])

    def test_issues_are_converted(self):
        llm = self.create_llm(self.create_response())
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].title, "Search Quality Issue")
        self.assertEqual(result.issues[0].severity, "Low")

    def test_recommendations_are_converted(self):
        llm = self.create_llm(self.create_response())
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.recommendations[0].title, "Improve Search Quality")

    def test_high_score_has_low_issue_severity(self):
        llm = self.create_llm(self.create_response(score=90))
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.issues[0].severity, "Low")

    def test_medium_score_has_medium_issue_severity(self):
        llm = self.create_llm(self.create_response(score=60))
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.issues[0].severity, "Medium")

    def test_low_score_has_high_issue_severity(self):
        llm = self.create_llm(self.create_response(score=30))
        evaluator = SearchQualityEvaluator(llm)
        result = evaluator.evaluate(self.create_content())

        self.assertEqual(result.issues[0].severity, "High")

    def test_llm_uses_structured_output(self):
        llm = self.create_llm(self.create_response())
        evaluator = SearchQualityEvaluator(llm)
        evaluator.evaluate(self.create_content())

        llm.with_structured_output.assert_called_once_with(SearchQualityLLMResult)