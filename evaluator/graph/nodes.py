import logging

from evaluator.evaluators.evaluation_report import EvaluationReport
from evaluator.services.evaluation_storage import save_evaluation
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


def content_extraction_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: content_extraction"
    )

    html = HTMLFetcher.fetch(
        state["url"]
    )

    soup = HTMLParser.parse(
        html
    )

    website_content = ContentExtractor.extract(
        state["url"],
        soup,
    )

    state["website_content"] = website_content

    logger.info(
        "Content extraction completed."
    )

    return state


def prompt_alignment_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: prompt_alignment"
    )

    evaluator = state[
        "prompt_alignment_evaluator"
    ]

    try:

        result = evaluator.evaluate(
            state["user_prompt"],
            state["website_content"],
        )

        logger.info(
            "Prompt alignment completed | score=%d",
            result.score,
        )

    except Exception as exc:

        logger.exception(
            "Prompt alignment failed."
        )

        result = PromptAlignmentResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Prompt alignment could not be evaluated",
                    description=(
                        "The prompt-alignment evaluator failed. "
                        f"Reason: {exc}"
                    ),
                )
            ],
            recommendations=[
                # Still make the failure visible.
            ],
        )

    return {
        "prompt_alignment": result,
    }


def knowledge_validation_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: knowledge_validation"
    )

    evaluator = state[
        "knowledge_validation_evaluator"
    ]

    try:

        result = evaluator.evaluate(
            state["website_content"]
        )

        logger.info(
            "Knowledge validation completed | score=%d",
            result.score,
        )

    except Exception as exc:

        logger.exception(
            "Knowledge validation failed."
        )

        result = KnowledgeValidationResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Knowledge validation could not be completed",
                    description=(
                        "The factual validation evaluator failed. "
                        f"Reason: {exc}"
                    ),
                )
            ],
            recommendations=[],
        )

    return {
        "knowledge_validation": result,
    }


def seo_quality_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: seo_quality"
    )

    evaluator = state[
        "seo_quality_evaluator"
    ]

    result = evaluator.evaluate(
        state["website_content"],
        user_prompt=state["user_prompt"],
    )

    logger.info(
        "SEO quality completed | score=%d",
        result.score,
    )

    return {
        "seo_quality": result,
    }


def search_quality_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: search_quality"
    )

    evaluator = state[
        "search_quality_evaluator"
    ]

    try:

        result = evaluator.evaluate(
            state["website_content"]
        )

        logger.info(
            "Search quality completed | score=%d",
            result.score,
        )

    except Exception as exc:

        logger.exception(
            "Search quality failed."
        )

        result = SearchQualityResult(
            score=0,
            issues=[
                Issue(
                    severity="High",
                    title="Search quality could not be evaluated",
                    description=(
                        "The search-quality evaluator failed. "
                        f"Reason: {exc}"
                    ),
                )
            ],
            recommendations=[],
        )

    return {
        "search_quality": result,
    }


def technical_html_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: technical_html"
    )

    evaluator = state[
        "technical_html_evaluator"
    ]

    result = evaluator.evaluate(
        state["website_content"]
    )

    logger.info(
        "Technical HTML completed | score=%d",
        result.score,
    )

    return {
        "technical_html": result,
    }


def score_aggregation_node(
    state: EvaluationState,
) -> EvaluationState:

    logger.info(
        "NODE: score_aggregation"
    )

    required = [
        "prompt_alignment",
        "knowledge_validation",
        "seo_quality",
        "search_quality",
        "technical_html",
    ]

    missing = [
        name
        for name in required
        if name not in state
    ]

    if missing:

        raise RuntimeError(
            "Cannot aggregate scores. "
            f"Missing evaluator results: {missing}"
        )

    aggregation = ScoreAggregator.aggregate(
        prompt_alignment=state[
            "prompt_alignment"
        ],
        knowledge_validation=state[
            "knowledge_validation"
        ],
        seo_quality=state[
            "seo_quality"
        ],
        search_quality=state[
            "search_quality"
        ],
        technical_html=state[
            "technical_html"
        ],
    )

    logger.info(
        "Scores | prompt=%d | knowledge=%d | seo=%d | search=%d | html=%d | final=%d",
        aggregation.prompt_alignment_score,
        aggregation.knowledge_validation_score,
        aggregation.seo_quality_score,
        aggregation.search_quality_score,
        aggregation.technical_html_score,
        aggregation.final_score,
    )


    report = EvaluationReport.from_results(
        aggregation=aggregation,
        prompt_alignment=state[
            "prompt_alignment"
        ],
        knowledge_validation=state[
            "knowledge_validation"
        ],
        seo_quality=state[
            "seo_quality"
        ],
        search_quality=state[
            "search_quality"
        ],
        technical_html=state[
            "technical_html"
        ],
    )

    state["evaluation_report"] = report

    save_evaluation(
        url=state["url"],
        prompt=state["user_prompt"],
        report=report,
    )

    return state


