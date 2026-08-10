from unittest.mock import Mock

from django.test import SimpleTestCase

from evaluator.graph.nodes import (
    knowledge_validation_node,
    prompt_alignment_node,
    search_quality_node,
)
from evaluator.graph.workflow import build_evaluation_graph


class EvaluationGraphTest(SimpleTestCase):

    def test_graph_builds_successfully(self):
        graph = build_evaluation_graph()

        self.assertIsNotNone(graph)

    def test_graph_contains_expected_nodes(self):
        graph = build_evaluation_graph()

        nodes = graph.nodes

        expected_nodes = {
            "prompt_alignment",
            "knowledge_validation",
            "seo_quality",
            "search_quality",
            "technical_html",
            "score_aggregation",
        }

        self.assertTrue(
            expected_nodes.issubset(nodes.keys())
        )

    def test_prompt_alignment_node_returns_fallback_when_evaluator_fails(self):
        evaluator = Mock()
        evaluator.evaluate.side_effect = RuntimeError("prompt failed")

        state = {
            "prompt_alignment_evaluator": evaluator,
            "user_prompt": "test prompt",
            "website_content": Mock(),
        }

        result = prompt_alignment_node(state)

        self.assertEqual(result["prompt_alignment"].score, 0)
        self.assertTrue(
            any("prompt failed" in issue.description for issue in result["prompt_alignment"].issues)
        )

    def test_knowledge_validation_node_returns_fallback_when_evaluator_fails(self):
        evaluator = Mock()
        evaluator.evaluate.side_effect = RuntimeError("knowledge failed")

        state = {
            "knowledge_validation_evaluator": evaluator,
            "website_content": Mock(),
        }

        result = knowledge_validation_node(state)

        self.assertEqual(result["knowledge_validation"].score, 0)
        self.assertTrue(
            any("knowledge failed" in issue.description for issue in result["knowledge_validation"].issues)
        )

    def test_search_quality_node_returns_fallback_when_evaluator_fails(self):
        evaluator = Mock()
        evaluator.evaluate.side_effect = RuntimeError("search failed")

        state = {
            "search_quality_evaluator": evaluator,
            "website_content": Mock(),
        }

        result = search_quality_node(state)

        self.assertEqual(result["search_quality"].score, 0)
        self.assertTrue(
            any("search failed" in issue.description for issue in result["search_quality"].issues)
        )