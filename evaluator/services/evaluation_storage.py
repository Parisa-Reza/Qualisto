from evaluator.models import Evaluation
from evaluator.evaluators.evaluation_report import EvaluationReport


def save_evaluation(
    *,
    url: str,
    prompt: str,
    report: EvaluationReport,
) -> Evaluation:
    """
    Save a completed evaluation report to PostgreSQL.
    """

    evaluation = Evaluation.objects.create(
        url=url,
        prompt=prompt,

        overall_score=report.final_score,

        prompt_alignment_score=(
            report.prompt_alignment.score
        ),

        knowledge_validation_score=(
            report.knowledge_validation.score
        ),

        seo_score=(
            report.seo_quality.score
        ),

        search_quality_score=(
            report.search_quality.score
        ),

        technical_html_score=(
            report.technical_html.score
        ),
    )

    return evaluation