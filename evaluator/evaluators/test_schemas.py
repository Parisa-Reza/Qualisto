from django.test import SimpleTestCase

from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    KnowledgeValidationResult,
    PromptAlignmentResult,
    Recommendation,
    SearchQualityResult,
)


class IssueTest(SimpleTestCase):

    def test_issue_creation(self):
        issue = Issue(
            severity="High",
            title="Broken Link",
            description="Homepage contains a broken link.",
        )

        self.assertEqual(issue.severity, "High")
        self.assertEqual(issue.title, "Broken Link")
        self.assertEqual(
            issue.description,
            "Homepage contains a broken link.",
        )


class RecommendationTest(SimpleTestCase):

    def test_recommendation_creation(self):
        recommendation = Recommendation(
            title="Fix Broken Link",
            description="Replace the invalid hyperlink.",
        )

        self.assertEqual(
            recommendation.title,
            "Fix Broken Link",
        )
        self.assertEqual(
            recommendation.description,
            "Replace the invalid hyperlink.",
        )


class EvaluationResultTest(SimpleTestCase):

    def test_default_lists_are_empty(self):
        result = EvaluationResult(score=90)

        self.assertEqual(result.score, 90)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.recommendations, [])


class PromptAlignmentResultTest(SimpleTestCase):

    def test_prompt_alignment_result(self):
        result = PromptAlignmentResult(
            score=85,
            missing_requirements=["Hotels"],
            off_topic_sections=["USA Visa"],
        )

        self.assertEqual(result.score, 85)
        self.assertEqual(
            result.missing_requirements,
            ["Hotels"],
        )
        self.assertEqual(
            result.off_topic_sections,
            ["USA Visa"],
        )


class KnowledgeValidationResultTest(SimpleTestCase):

    def test_knowledge_validation_result(self):
        result = KnowledgeValidationResult(
            score=80,
            verified_claims=["Bali is in Indonesia"],
            unsupported_claims=["Bali is in Thailand"],
            uncertain_claims=["10 million tourists annually"],
        )

        self.assertEqual(result.score, 80)
        self.assertEqual(
            result.verified_claims,
            ["Bali is in Indonesia"],
        )
        self.assertEqual(
            result.unsupported_claims,
            ["Bali is in Thailand"],
        )
        self.assertEqual(
            result.uncertain_claims,
            ["10 million tourists annually"],
        )


class SearchQualityResultTest(SimpleTestCase):

    def test_search_quality_result(self):
        result = SearchQualityResult(
            score=91,
            search_intent="Informational",
            helpfulness_score=90,
            completeness_score=88,
            natural_writing_score=95,
            repetition_score=92,
            ai_sounding_score=89,
            content_depth_score=87,
            readability_score=93,
            user_satisfaction_score=90,
            missing_sections=["Transportation"],
        )

        self.assertEqual(result.score, 91)
        self.assertEqual(
            result.search_intent,
            "Informational",
        )
        self.assertEqual(
            result.helpfulness_score,
            90,
        )
        self.assertEqual(
            result.completeness_score,
            88,
        )
        self.assertEqual(
            result.natural_writing_score,
            95,
        )
        self.assertEqual(
            result.repetition_score,
            92,
        )
        self.assertEqual(
            result.ai_sounding_score,
            89,
        )
        self.assertEqual(
            result.content_depth_score,
            87,
        )
        self.assertEqual(
            result.readability_score,
            93,
        )
        self.assertEqual(
            result.user_satisfaction_score,
            90,
        )
        self.assertEqual(
            result.missing_sections,
            ["Transportation"],
        )