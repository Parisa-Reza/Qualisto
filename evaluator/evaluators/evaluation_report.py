from dataclasses import dataclass, field

from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    Recommendation,
)
from evaluator.evaluators.score_aggregator import ScoreAggregationResult


@dataclass(slots=True)
class EvaluationReport:
    """
    Unified result returned by the complete Qualisto evaluator.

    Each evaluation module keeps its own score out of 100.
    The final_score is the aggregated score out of 100.
    """

    final_score: int

    prompt_alignment: EvaluationResult
    knowledge_validation: EvaluationResult
    seo_quality: EvaluationResult
    search_quality: EvaluationResult
    technical_html: EvaluationResult

    issues: list[Issue] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)

    @classmethod
    def from_results(
        cls,
        *,
        aggregation: ScoreAggregationResult,
        prompt_alignment: EvaluationResult,
        knowledge_validation: EvaluationResult,
        seo_quality: EvaluationResult,
        search_quality: EvaluationResult,
        technical_html: EvaluationResult,
    ) -> "EvaluationReport":

        issues = [
            *prompt_alignment.issues,
            *knowledge_validation.issues,
            *seo_quality.issues,
            *search_quality.issues,
            *technical_html.issues,
        ]

        recommendations = [
            *prompt_alignment.recommendations,
            *knowledge_validation.recommendations,
            *seo_quality.recommendations,
            *search_quality.recommendations,
            *technical_html.recommendations,
        ]

        return cls(
            final_score=aggregation.final_score,
            prompt_alignment=prompt_alignment,
            knowledge_validation=knowledge_validation,
            seo_quality=seo_quality,
            search_quality=search_quality,
            technical_html=technical_html,
            issues=issues,
            recommendations=recommendations,
        )