from langgraph.graph import END, START, StateGraph

from evaluator.graph.nodes import (
    knowledge_validation_node,
    prompt_alignment_node,
    score_aggregation_node,
    search_quality_node,
    seo_quality_node,
    technical_html_node,
)
from evaluator.graph.state import EvaluationState


def build_evaluation_graph():
    """
    Build the complete Qualisto evaluation workflow.
    """
    graph = StateGraph(EvaluationState)

    graph.add_node("prompt_alignment", prompt_alignment_node)
    graph.add_node("knowledge_validation", knowledge_validation_node)
    graph.add_node("seo_quality", seo_quality_node)
    graph.add_node("search_quality", search_quality_node)
    graph.add_node("technical_html", technical_html_node)
    graph.add_node("score_aggregation", score_aggregation_node)

    graph.add_edge(START, "prompt_alignment")
    graph.add_edge("prompt_alignment", "knowledge_validation")
    graph.add_edge("knowledge_validation", "seo_quality")
    graph.add_edge("seo_quality", "search_quality")
    graph.add_edge("search_quality", "technical_html")
    graph.add_edge("technical_html", "score_aggregation")
    graph.add_edge("score_aggregation", END)

    return graph.compile()