"""
End-to-end webpage evaluation service.

This is the single application-level entry point for running the complete Qualisto evaluation pipeline.

Flow:

user_prompt + url
        ↓
LangGraph workflow
        ↓
individual evaluators
        ↓
score aggregation
        ↓
evaluation report
"""

from __future__ import annotations

from typing import Any

from evaluator.graph.workflow import evaluation_graph


class EvaluationService:
    """
    Application service responsible for executing the complete
    webpage evaluation workflow.
    """

    def __init__(self, graph: Any | None = None) -> None:
        """
        Initialize the evaluation service.

        Args:
            graph:
                Optional compiled LangGraph workflow.Dependency injection is supported so tests can provide a fake graph without calling external services.
        """
        self._graph = graph or evaluation_graph

    def evaluate( self, *, url: str, user_prompt: str) -> dict[str, Any]:
        """
        Evaluate a webpage against the user's prompt.

        Args:
            url: URL of the webpage to evaluate.
            user_prompt: Original prompt describing the requested webpage.

        Returns:
            Final evaluation result produced by the LangGraph workflow.

        Raises:
            ValueError:
                If URL or user prompt is empty.
        """

        self._validate_input(
            url=url,
            user_prompt=user_prompt,
        )

        initial_state = {
            "url": url.strip(),
            "user_prompt": user_prompt.strip(),
        }

        result = self._graph.invoke(initial_state)

        if not isinstance(result, dict):
            raise TypeError(
                "Evaluation workflow must return a dictionary state."
            )

        return result

    @staticmethod
    def _validate_input(*, url: str, user_prompt: str,) -> None:
        """Validate required evaluation inputs."""

        if not isinstance(url, str) or not url.strip():
            raise ValueError("URL must be a non-empty string.")

        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError(
                "User prompt must be a non-empty string."
            )


def evaluate_webpage( *, url: str, user_prompt: str) -> dict[str, Any]:
    """
    Convenience function for callers that do not need to instantiate EvaluationService explicitly.
    """

    service = EvaluationService()

    return service.evaluate(
        url=url,
        user_prompt=user_prompt,
    )