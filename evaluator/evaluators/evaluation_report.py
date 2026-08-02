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

    def to_dict(self) -> dict:
        """
        Convert the unified evaluation report into a JSON-serializable
        dictionary for the Django API.
        """

        def result_to_dict(
            result: EvaluationResult,
        ) -> dict:
            return {
                "score": result.score,
                "issues": [
                    {
                        "severity": issue.severity,
                        "title": issue.title,
                        "description": issue.description,
                    }
                    for issue in result.issues
                ],
                "recommendations": [
                    {
                        "title": recommendation.title,
                        "description": recommendation.description,
                    }
                    for recommendation in result.recommendations
                ],
            }

        return {
            "overall_score": self.final_score,

            "scores": {
                "prompt_alignment": (
                    self.prompt_alignment.score
                ),
                "knowledge_validation": (
                    self.knowledge_validation.score
                ),
                "seo_quality": (
                    self.seo_quality.score
                ),
                "search_quality": (
                    self.search_quality.score
                ),
                "technical_html": (
                    self.technical_html.score
                ),
            },

            "issues": [
                {
                    "severity": issue.severity,
                    "title": issue.title,
                    "description": issue.description,
                }
                for issue in self.issues
            ],

            "recommendations": [
                {
                    "title": recommendation.title,
                    "description": recommendation.description,
                }
                for recommendation in self.recommendations
            ],

            # Keep individual evaluator details available
            # for future report/UI expansion.
            "evaluations": {
                "prompt_alignment": result_to_dict(
                    self.prompt_alignment
                ),
                "knowledge_validation": result_to_dict(
                    self.knowledge_validation
                ),
                "seo_quality": result_to_dict(
                    self.seo_quality
                ),
                "search_quality": result_to_dict(
                    self.search_quality
                ),
                "technical_html": result_to_dict(
                    self.technical_html
                ),
            },
        }