from evaluator.evaluators.evaluation_report import EvaluationReport
from evaluator.evaluators.score_aggregator import ScoreAggregator

from evaluator.extractor.fetcher import HTMLFetcher
from evaluator.extractor.parser import HTMLParser
from evaluator.extractor.content_extractor import ContentExtractor

from evaluator.graph.state import EvaluationState


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

    state["prompt_alignment"] = evaluator.evaluate(
        state["user_prompt"],
        state["website_content"],
    )

    return state


def knowledge_validation_node(state: EvaluationState) -> EvaluationState:
    """
    Run knowledge-validation evaluation.
    """

    evaluator = state["knowledge_validation_evaluator"]

    state["knowledge_validation"] = evaluator.evaluate(
        state["website_content"],
    )

    return state


def seo_quality_node(state: EvaluationState) -> EvaluationState:
    """
    Run SEO-quality evaluation.
    """

    evaluator = state["seo_quality_evaluator"]

    state["seo_quality"] = evaluator.evaluate(
        state["website_content"],
        user_prompt=state["user_prompt"],
    )

    return state


def search_quality_node(state: EvaluationState) -> EvaluationState:
    """
    Run search-quality evaluation.
    """

    evaluator = state["search_quality_evaluator"]

    state["search_quality"] = evaluator.evaluate(
        state["website_content"],
    )

    return state


def technical_html_node(state: EvaluationState) -> EvaluationState:
    """
    Run technical HTML evaluation.
    """

    evaluator = state["technical_html_evaluator"]

    state["technical_html"] = evaluator.evaluate(
        state["website_content"],
    )

    return state


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