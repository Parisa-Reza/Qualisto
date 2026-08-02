from django.test import SimpleTestCase

from evaluator.evaluators.schemas import EvaluationResult
from evaluator.evaluators.score_aggregator import ScoreAggregator


class ScoreAggregatorTest(SimpleTestCase):

    @staticmethod
    def result(score):
        return EvaluationResult(score=score)

    def test_equal_weight_average(self):
        result = ScoreAggregator.aggregate(
            prompt_alignment=self.result(80),
            knowledge_validation=self.result(90),
            seo_quality=self.result(70),
            search_quality=self.result(60),
            technical_html=self.result(100),
        )

        self.assertEqual(result.prompt_alignment_score, 80)
        self.assertEqual(result.knowledge_validation_score, 90)
        self.assertEqual(result.seo_quality_score, 70)
        self.assertEqual(result.search_quality_score, 60)
        self.assertEqual(result.technical_html_score, 100)

        self.assertEqual(result.final_score, 80)

    def test_perfect_scores(self):
        result = ScoreAggregator.aggregate(
            prompt_alignment=self.result(100),
            knowledge_validation=self.result(100),
            seo_quality=self.result(100),
            search_quality=self.result(100),
            technical_html=self.result(100),
        )

        self.assertEqual(result.final_score, 100)

    def test_zero_scores(self):
        result = ScoreAggregator.aggregate(
            prompt_alignment=self.result(0),
            knowledge_validation=self.result(0),
            seo_quality=self.result(0),
            search_quality=self.result(0),
            technical_html=self.result(0),
        )

        self.assertEqual(result.final_score, 0)

    def test_fractional_average_is_rounded_half_up(self):
        result = ScoreAggregator.aggregate(
            prompt_alignment=self.result(81),
            knowledge_validation=self.result(82),
            seo_quality=self.result(83),
            search_quality=self.result(84),
            technical_html=self.result(85),
        )

        # Average = 83.0
        self.assertEqual(result.final_score, 83)

    def test_score_below_zero_is_rejected(self):
        with self.assertRaises(ValueError):
            ScoreAggregator.aggregate(
                prompt_alignment=self.result(-1),
                knowledge_validation=self.result(80),
                seo_quality=self.result(80),
                search_quality=self.result(80),
                technical_html=self.result(80),
            )

    def test_score_above_100_is_rejected(self):
        with self.assertRaises(ValueError):
            ScoreAggregator.aggregate(
                prompt_alignment=self.result(101),
                knowledge_validation=self.result(80),
                seo_quality=self.result(80),
                search_quality=self.result(80),
                technical_html=self.result(80),
            )

    def test_non_integer_score_is_rejected(self):
        with self.assertRaises(TypeError):
            ScoreAggregator.aggregate(
                prompt_alignment=EvaluationResult(score=80.5),
                knowledge_validation=self.result(80),
                seo_quality=self.result(80),
                search_quality=self.result(80),
                technical_html=self.result(80),
            )