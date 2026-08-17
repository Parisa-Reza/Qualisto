"""
End-to-end webpage evaluation service.
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from google import genai

from evaluator.evaluators.knowledge_validation import (
    KnowledgeValidationEvaluator,
)
from evaluator.evaluators.prompt_alignment import (
    PromptAlignmentEvaluator,
)
from evaluator.evaluators.search_quality import (
    SearchQualityEvaluator,
)
from evaluator.evaluators.seo_content_quality import (
    SEOQualityEvaluator,
)
from evaluator.evaluators.technical_html import (
    TechnicalHTMLEvaluator,
)
from evaluator.graph.workflow import evaluation_graph


logger = logging.getLogger(__name__)


class EvaluationService:
    """
    Application service responsible for executing the complete
    webpage evaluation workflow.

    Parameters:
        graph: LangGraph evaluation workflow.
        llm: Ollama/text LLM used by the evaluators.
        search_client: Tavily search client.
        gemini_client: Gemini client used for hero-image validation.
    """

    def __init__(
        self,
        graph: Any | None = None,
        *,
        llm: Any | None = None,
        search_client: Any | None = None,
        gemini_client: Any | None = None,
    ) -> None:

        self._using_default_graph = graph is None

        self._graph = (
            evaluation_graph
            if graph is None
            else graph
        )

        self._llm = llm
        self._search_client = search_client
        self._gemini_client = gemini_client

        logger.info(
            "EvaluationService initialized | "
            "default_graph=%s | llm=%s | search_client=%s | "
            "gemini_enabled=%s",
            self._using_default_graph,
            type(llm).__name__ if llm else None,
            type(search_client).__name__
            if search_client
            else None,
            bool(gemini_client),
        )

    def evaluate(
        self,
        *,
        url: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """
        Execute the complete webpage evaluation workflow.

        Parameters:
            url: URL of the webpage to evaluate.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Final LangGraph evaluation state.
        """

        logger.info(
            "Evaluation started | url=%s",
            url,
        )

        self._validate_input(
            url=url,
            user_prompt=user_prompt,
        )

        initial_state: dict[str, Any] = {
            "url": url.strip(),
            "user_prompt": user_prompt.strip(),
        }

        logger.info(
            "Initial evaluation state created | "
            "url=%s | prompt_length=%d",
            initial_state["url"],
            len(initial_state["user_prompt"]),
        )

        # ----------------------------------------------------------
        # INJECTED GRAPH
        # ----------------------------------------------------------
        #
        # Tests and custom integrations can inject a fake graph.
        # In that case, external dependencies are intentionally
        # not required.
        # ----------------------------------------------------------

        if not self._using_default_graph:

            logger.info(
                "Using injected evaluation graph."
            )

            result = self._graph.invoke(
                initial_state
            )

            if not isinstance(result, dict):
                logger.error(
                    "Evaluation workflow returned invalid "
                    "result type: %s",
                    type(result).__name__,
                )

                raise TypeError(
                    "Evaluation workflow must return "
                    "a dictionary state."
                )

            logger.info(
                "Evaluation completed using injected graph."
            )

            return result

        # ----------------------------------------------------------
        # REQUIRED DEPENDENCIES
        # ----------------------------------------------------------

        if self._llm is None:
            logger.error(
                "Evaluation failed: LLM is missing."
            )

            raise RuntimeError(
                "LLM is required to run the evaluation workflow."
            )

        if self._search_client is None:
            logger.error(
                "Evaluation failed: search client is missing."
            )

            raise RuntimeError(
                "Search client is required to run knowledge validation."
            )

        if self._gemini_client is None:
            logger.error(
                "Evaluation failed: Gemini client is missing."
            )

            raise RuntimeError(
                "Gemini client is required for hero image validation."
            )

        # ----------------------------------------------------------
        # CREATE EVALUATORS
        # ----------------------------------------------------------

        logger.info(
            "Creating evaluator instances."
        )

        initial_state.update(
            {
                "prompt_alignment_evaluator": (
                    PromptAlignmentEvaluator(
                        llm=self._llm,
                    )
                ),

                "knowledge_validation_evaluator": (
                    KnowledgeValidationEvaluator(
                        llm=self._llm,
                        search_client=self._search_client,
                        gemini_client=self._gemini_client,
                        gemini_model=(
                            settings.GEMINI_IMAGE_MODEL
                        ),
                    )
                ),

                "seo_quality_evaluator": (
                    SEOQualityEvaluator(
                        llm=self._llm,
                    )
                ),

                "search_quality_evaluator": (
                    SearchQualityEvaluator(
                        llm=self._llm,
                    )
                ),

                "technical_html_evaluator": (
                    TechnicalHTMLEvaluator()
                ),
            }
        )

        logger.info(
            "All evaluator instances created."
        )

        # ----------------------------------------------------------
        # RUN LANGGRAPH
        # ----------------------------------------------------------

        logger.info(
            "Starting LangGraph evaluation workflow."
        )

        try:

            result = self._graph.invoke(
                initial_state
            )

        except Exception:

            logger.exception(
                "Evaluation workflow failed."
            )

            raise

        if not isinstance(result, dict):
            logger.error(
                "Evaluation workflow returned invalid "
                "result type: %s",
                type(result).__name__,
            )

            raise TypeError(
                "Evaluation workflow must return "
                "a dictionary state."
            )

        logger.info(
            "LangGraph evaluation workflow completed."
        )

        logger.info(
            "Evaluation finished successfully."
        )

        return result

    @staticmethod
    def _validate_input(
        *,
        url: str,
        user_prompt: str,
    ) -> None:
        """Validate evaluation inputs."""

        logger.debug(
            "Validating evaluation input."
        )

        if (
            not isinstance(url, str)
            or not url.strip()
        ):
            logger.warning(
                "Invalid evaluation input: URL is empty."
            )

            raise ValueError(
                "URL must be a non-empty string."
            )

        if (
            not isinstance(user_prompt, str)
            or not user_prompt.strip()
        ):
            logger.warning(
                "Invalid evaluation input: "
                "user prompt is empty."
            )

            raise ValueError(
                "User prompt must be a non-empty string."
            )

        logger.debug(
            "Evaluation input validation passed."
        )


def evaluate_webpage(
    *,
    url: str,
    user_prompt: str,
    llm: Any | None = None,
    search_client: Any | None = None,
) -> dict[str, Any]:
    """
    Convenience function for running webpage evaluation.

    This function creates the Gemini client because Gemini is used
    exclusively for multimodal hero-image validation.
    """

    logger.info(
        "evaluate_webpage() called | url=%s",
        url,
    )

    # --------------------------------------------------------------
    # GEMINI CLIENT
    # --------------------------------------------------------------
    #
    # This is the single place where the convenience API creates
    # the Gemini client.
    # --------------------------------------------------------------

    gemini_api_key = getattr(
        settings,
        "GEMINI_API_KEY",
        "",
    )

    if not gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    gemini_client = genai.Client(
        api_key=gemini_api_key,
    )

    # --------------------------------------------------------------
    # EVALUATION SERVICE
    # --------------------------------------------------------------

    service = EvaluationService(
        llm=llm,
        search_client=search_client,
        gemini_client=gemini_client,
    )

    return service.evaluate(
        url=url,
        user_prompt=user_prompt,
    )