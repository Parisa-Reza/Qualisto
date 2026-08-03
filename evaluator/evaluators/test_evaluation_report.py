from django.test import SimpleTestCase

from evaluator.evaluators.evaluation_report import EvaluationReport
from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    Recommendation,
)
from evaluator.evaluators.score_aggregator import ScoreAggregator


class EvaluationReportTest(SimpleTestCase):

    def create_result(self, score, issue_title, recommendation_title):
        return EvaluationResult(
            score=score,
            issues=[
                Issue(
                    severity="Medium",
                    title=issue_title,
                    description="Test issue.",
                )
            ],
            recommendations=[
                Recommendation(
                    title=recommendation_title,
                    description="Test recommendation.",
                )
            ],
        )

    def test_report_contains_all_module_results(self):
        prompt_alignment = self.create_result(
            80,
            "Prompt Issue",
            "Prompt Recommendation",
        )

        knowledge_validation = self.create_result(
            90,
            "Knowledge Issue",
            "Knowledge Recommendation",
        )

        seo_quality = self.create_result(
            70,
            "SEO Issue",
            "SEO Recommendation",
        )

        search_quality = self.create_result(
            60,
            "Search Issue",
            "Search Recommendation",
        )

        technical_html = self.create_result(
            100,
            "HTML Issue",
            "HTML Recommendation",
        )

        aggregation = ScoreAggregator.aggregate(
            prompt_alignment=prompt_alignment,
            knowledge_validation=knowledge_validation,
            seo_quality=seo_quality,
            search_quality=search_quality,
            technical_html=technical_html,
        )

        report = EvaluationReport.from_results(
            aggregation=aggregation,
            prompt_alignment=prompt_alignment,
            knowledge_validation=knowledge_validation,
            seo_quality=seo_quality,
            search_quality=search_quality,
            technical_html=technical_html,
        )

        self.assertEqual(report.final_score, 80)

        self.assertEqual(report.prompt_alignment.score, 80)
        self.assertEqual(report.knowledge_validation.score, 90)
        self.assertEqual(report.seo_quality.score, 70)
        self.assertEqual(report.search_quality.score, 60)
        self.assertEqual(report.technical_html.score, 100)

    def test_report_combines_all_issues(self):
        results = [
            self.create_result(80, "Issue 1", "Recommendation 1"),
            self.create_result(80, "Issue 2", "Recommendation 2"),
            self.create_result(80, "Issue 3", "Recommendation 3"),
            self.create_result(80, "Issue 4", "Recommendation 4"),
            self.create_result(80, "Issue 5", "Recommendation 5"),
        ]

        aggregation = ScoreAggregator.aggregate(
            prompt_alignment=results[0],
            knowledge_validation=results[1],
            seo_quality=results[2],
            search_quality=results[3],
            technical_html=results[4],
        )

        report = EvaluationReport.from_results(
            aggregation=aggregation,
            prompt_alignment=results[0],
            knowledge_validation=results[1],
            seo_quality=results[2],
            search_quality=results[3],
            technical_html=results[4],
        )

        self.assertEqual(len(report.issues), 5)
        self.assertEqual(len(report.recommendations), 5)

    def test_report_final_score_is_100_for_perfect_results(self):
        result = EvaluationResult(score=100)

        aggregation = ScoreAggregator.aggregate(
            prompt_alignment=result,
            knowledge_validation=result,
            seo_quality=result,
            search_quality=result,
            technical_html=result,
        )

        report = EvaluationReport.from_results(
            aggregation=aggregation,
            prompt_alignment=result,
            knowledge_validation=result,
            seo_quality=result,
            search_quality=result,
            technical_html=result,
        )

        self.assertEqual(report.final_score, 100)