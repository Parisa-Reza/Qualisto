from django.test import SimpleTestCase

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