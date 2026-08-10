from unittest.mock import Mock

from django.test import SimpleTestCase

from evaluator.e2e_service.evaluator import EvaluationService


class EvaluationServiceTest(SimpleTestCase):
    """Tests for the end-to-end evaluation service."""

    def test_evaluate_invokes_workflow(self):
        graph = Mock()

        expected_result = {
            "url": "https://example.com",
            "user_prompt": "Create a travel page about Bali.",
            "final_score": 85,
        }

        graph.invoke.return_value = expected_result

        service = EvaluationService(
            graph=graph
        )

        result = service.evaluate(
            url="https://example.com",
            user_prompt="Create a travel page about Bali.",
        )

        graph.invoke.assert_called_once_with(
            {
                "url": "https://example.com",
                "user_prompt": "Create a travel page about Bali.",
            }
        )

        self.assertEqual(
            result,
            expected_result,
        )

    def test_url_is_required(self):
        graph = Mock()

        service = EvaluationService(
            graph=graph
        )

        with self.assertRaises(ValueError):

            service.evaluate(
                url="",
                user_prompt="Create a travel page about Bali.",
            )

        graph.invoke.assert_not_called()

    def test_user_prompt_is_required(self):
        graph = Mock()

        service = EvaluationService(
            graph=graph
        )

        with self.assertRaises(ValueError):

            service.evaluate(
                url="https://example.com",
                user_prompt="",
            )

        graph.invoke.assert_not_called()

    def test_url_is_stripped(self):
        graph = Mock()
        graph.invoke.return_value = {}

        service = EvaluationService(
            graph=graph
        )

        service.evaluate(
            url="  https://example.com  ",
            user_prompt="  Create a Bali page.  ",
        )

        graph.invoke.assert_called_once_with(
            {
                "url": "https://example.com",
                "user_prompt": "Create a Bali page.",
            }
        )

    def test_workflow_result_must_be_dictionary(self):
        graph = Mock()
        graph.invoke.return_value = "invalid result"

        service = EvaluationService(
            graph=graph
        )

        with self.assertRaises(TypeError):

            service.evaluate(
                url="https://example.com",
                user_prompt="Create a Bali page.",
            )

    def test_non_string_url_is_rejected(self):
        graph = Mock()

        service = EvaluationService(
            graph=graph
        )

        with self.assertRaises(ValueError):

            service.evaluate(
                url=None,
                user_prompt="Create a Bali page.",
            )

        graph.invoke.assert_not_called()

    def test_non_string_prompt_is_rejected(self):
        graph = Mock()

        service = EvaluationService(
            graph=graph
        )

        with self.assertRaises(ValueError):

            service.evaluate(
                url="https://example.com",
                user_prompt=None,
            )

        graph.invoke.assert_not_called()