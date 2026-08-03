import logging

from evaluator.evaluators.evaluation_report import EvaluationReport
from evaluator.evaluators.score_aggregator import ScoreAggregator
from evaluator.evaluators.schemas import (
    Issue,
    KnowledgeValidationResult,
    PromptAlignmentResult,
    SearchQualityResult,
)

from evaluator.extractor.fetcher import HTMLFetcher
from evaluator.extractor.parser import HTMLParser
from evaluator.extractor.content_extractor import ContentExtractor

from evaluator.graph.state import EvaluationState


logger = logging.getLogger(__name__)


def content_extraction_node(state: EvaluationState) -> EvaluationState:
    """
    Fetch webpage HTML and extract structured website content.
    """

    html = HTMLFetcher.fetch(state["url"])

    soup = HTMLParser.parse(html)

    website_content = ContentExtractor.extract(
        state["url"],
        soup,
    )

    state["website_content"] = website_content

    return state


def prompt_alignment_node(state: EvaluationState) -> EvaluationState:
    """
    Run prompt-alignment evaluation.
    """

    evaluator = state["prompt_alignment_evaluator"]

    try:
        result = evaluator.evaluate(
            state["user_prompt"],
            state["website_content"],
        )
    except Exception as exc:
        logger.exception(
            "Prompt alignment evaluation failed; using fallback result."
        )
        result = PromptAlignmentResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Prompt Alignment Evaluation Failed",
                    description=str(exc),
                )
            ],
            recommendations=[],
        )

    return {
        "prompt_alignment": result,
    }


def knowledge_validation_node(state: EvaluationState) -> EvaluationState:
    """
    Run knowledge-validation evaluation.
    """

    evaluator = state["knowledge_validation_evaluator"]

    try:
        result = evaluator.evaluate(
            state["website_content"],
        )
    except Exception as exc:
        logger.exception(
            "Knowledge validation evaluation failed; using fallback result."
        )
        result = KnowledgeValidationResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Knowledge Validation Evaluation Failed",
                    description=str(exc),
                )
            ],
            recommendations=[],
        )

    return {
        "knowledge_validation": result,
    }


def seo_quality_node(state: EvaluationState) -> EvaluationState:
    """
    Run SEO-quality evaluation.
    """

    evaluator = state["seo_quality_evaluator"]

    result = evaluator.evaluate(
        state["website_content"],
        user_prompt=state["user_prompt"],
    )

    return {
        "seo_quality": result,
    }


def search_quality_node(state: EvaluationState) -> EvaluationState:
    """
    Run search-quality evaluation.
    """

    evaluator = state["search_quality_evaluator"]

    try:
        result = evaluator.evaluate(
            state["website_content"],
        )
    except Exception as exc:
        logger.exception(
            "Search quality evaluation failed; using fallback result."
        )
        result = SearchQualityResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Search Quality Evaluation Failed",
                    description=str(exc),
                )
            ],
            recommendations=[],
        )

    return {
        "search_quality": result,
    }


def technical_html_node(state: EvaluationState) -> EvaluationState:
    """
    Run technical HTML evaluation.
    """

    evaluator = state["technical_html_evaluator"]

    result = evaluator.evaluate(
        state["website_content"],
    )

    return {
        "technical_html": result,
    }


def score_aggregation_node(state: EvaluationState) -> EvaluationState:
    """
    Aggregate all five evaluator scores and create
    the unified evaluation report.
    """

    aggregation = ScoreAggregator.aggregate(
        prompt_alignment=state["prompt_alignment"],
        knowledge_validation=state["knowledge_validation"],
        seo_quality=state["seo_quality"],
        search_quality=state["search_quality"],
        technical_html=state["technical_html"],
    )

    state["evaluation_report"] = EvaluationReport.from_results(
        aggregation=aggregation,
        prompt_alignment=state["prompt_alignment"],
        knowledge_validation=state["knowledge_validation"],
        seo_quality=state["seo_quality"],
        search_quality=state["search_quality"],
        technical_html=state["technical_html"],
    )

    return state