from typing import TypedDict

from evaluator.evaluators.evaluation_report import EvaluationReport
from evaluator.evaluators.schemas import EvaluationResult
from evaluator.extractor.schemas import WebsiteContent


class EvaluationState(TypedDict, total=False):
    """
    Shared state passed between LangGraph nodes.
    """

    user_prompt: str
    url: str

    website_content: WebsiteContent

    prompt_alignment_evaluator: object
    knowledge_validation_evaluator: object
    seo_quality_evaluator: object
    search_quality_evaluator: object
    technical_html_evaluator: object

    prompt_alignment: EvaluationResult
    knowledge_validation: EvaluationResult
    seo_quality: EvaluationResult
    search_quality: EvaluationResult
    technical_html: EvaluationResult

    evaluation_report: EvaluationReport

    error: str