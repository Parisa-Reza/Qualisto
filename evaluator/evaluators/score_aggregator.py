from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from evaluator.evaluators.schemas import EvaluationResult


@dataclass(slots=True, frozen=True)
class ScoreAggregationResult:
    """
    Aggregated score for the five evaluation modules.

    Every module contributes equally to the final score.
    """

    prompt_alignment_score: int
    knowledge_validation_score: int
    seo_quality_score: int
    search_quality_score: int
    technical_html_score: int
    final_score: int


class ScoreAggregator:
    """
    Aggregates the scores produced by the five evaluators.

    Final score:
        (module_1 + module_2 + module_3 + module_4 + module_5) / 5

    Every module score is expected to be between 0 and 100.
    """

    REQUIRED_MODULES = (
        "prompt_alignment",
        "knowledge_validation",
        "seo_quality",
        "search_quality",
        "technical_html",
    )

    @classmethod
    def aggregate(
        cls,
        *,
        prompt_alignment: EvaluationResult,
        knowledge_validation: EvaluationResult,
        seo_quality: EvaluationResult,
        search_quality: EvaluationResult,
        technical_html: EvaluationResult,
    ) -> ScoreAggregationResult:

        scores = {
            "prompt_alignment": prompt_alignment.score,
            "knowledge_validation": knowledge_validation.score,
            "seo_quality": seo_quality.score,
            "search_quality": search_quality.score,
            "technical_html": technical_html.score,
        }

        cls._validate_scores(scores)

        final_score = cls._calculate_final_score(scores)

        return ScoreAggregationResult(
            prompt_alignment_score=scores["prompt_alignment"],
            knowledge_validation_score=scores["knowledge_validation"],
            seo_quality_score=scores["seo_quality"],
            search_quality_score=scores["search_quality"],
            technical_html_score=scores["technical_html"],
            final_score=final_score,
        )

    @staticmethod
    def _validate_scores(scores: dict[str, int]) -> None:
        for module_name, score in scores.items():
            if not isinstance(score, int):
                raise TypeError(
                    f"{module_name} score must be an integer, "
                    f"got {type(score).__name__}."
                )

            if not 0 <= score <= 100:
                raise ValueError(
                    f"{module_name} score must be between 0 and 100, "
                    f"got {score}."
                )

    @staticmethod
    def _calculate_final_score(scores: dict[str, int]) -> int:
        average = Decimal(sum(scores.values())) / Decimal(len(scores))

        return int(
            average.quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )