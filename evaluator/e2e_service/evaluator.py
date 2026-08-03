
"""
End-to-end webpage evaluation service.
"""

from __future__ import annotations

import logging
from typing import Any

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
    """

    def __init__(
        self,
        graph: Any | None = None,
        *,
        llm: Any | None = None,
        search_client: Any | None = None,
    ) -> None:

        self._using_default_graph = graph is None

        self._graph = (
            evaluation_graph
            if graph is None
            else graph
        )

        self._llm = llm
        self._search_client = search_client

        logger.info(
            "EvaluationService initialized | default_graph=%s | llm=%s | search_client=%s",
            self._using_default_graph,
            type(llm).__name__ if llm else None,
            type(search_client).__name__ if search_client else None,
        )

    def evaluate(
        self,
        *,
        url: str,
        user_prompt: str,
    ) -> dict[str, Any]:

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
            "Initial evaluation state created | url=%s | prompt_length=%d",
            initial_state["url"],
            len(initial_state["user_prompt"]),
        )

        # When a fake graph is injected, keep the service
        # completely independent of external dependencies.
        if not self._using_default_graph:

            logger.info(
                "Using injected evaluation graph."
            )

            result = self._graph.invoke(initial_state)

            if not isinstance(result, dict):
                logger.error(
                    "Evaluation workflow returned invalid result type: %s",
                    type(result).__name__,
                )
                raise TypeError(
                    "Evaluation workflow must return a dictionary state."
                )

            logger.info(
                "Evaluation completed using injected graph."
            )

            return result

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

        logger.info(
            "Creating evaluator instances."
        )

        initial_state.update(
            {
                "prompt_alignment_evaluator": (
                    PromptAlignmentEvaluator(
                        llm=self._llm
                    )
                ),
                "knowledge_validation_evaluator": (
                    KnowledgeValidationEvaluator(
                        llm=self._llm,
                        search_client=self._search_client,
                    )
                ),
                "seo_quality_evaluator": (
                    SEOQualityEvaluator()
                ),
                "search_quality_evaluator": (
                    SearchQualityEvaluator(
                        llm=self._llm
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

        logger.info(
            "Starting LangGraph evaluation workflow."
        )

        try:

            result = self._graph.invoke(initial_state)

        except Exception:

            logger.exception(
                "Evaluation workflow failed."
            )

            raise

        if not isinstance(result, dict):
            logger.error(
                "Evaluation workflow returned invalid result type: %s",
                type(result).__name__,
            )
            raise TypeError(
                "Evaluation workflow must return a dictionary state."
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

        logger.debug(
            "Validating evaluation input."
        )

        if not isinstance(url, str) or not url.strip():
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
                "Invalid evaluation input: user prompt is empty."
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

    logger.info(
        "evaluate_webpage() called | url=%s",
        url,
    )

    service = EvaluationService(
        llm=llm,
        search_client=search_client,
    )

    return service.evaluate(
        url=url,
        user_prompt=user_prompt,
    )



# """
# End-to-end webpage evaluation service.
# """

# from __future__ import annotations

# import os
# from typing import Any

# from evaluator.evaluators.knowledge_validation import (
#     KnowledgeValidationEvaluator,
# )
# from evaluator.evaluators.prompt_alignment import (
#     PromptAlignmentEvaluator,
# )
# from evaluator.evaluators.search_quality import (
#     SearchQualityEvaluator,
# )
# from evaluator.evaluators.seo_content_quality import (
#     SEOQualityEvaluator,
# )
# from evaluator.evaluators.technical_html import (
#     TechnicalHTMLEvaluator,
# )

# from evaluator.graph.workflow import evaluation_graph


# class EvaluationService:
#     """
#     Application service responsible for executing the complete
#     webpage evaluation workflow.
#     """

#     def __init__(
#         self,
#         graph: Any | None = None,
#         *,
#         llm: Any | None = None,
#         search_client: Any | None = None,
#     ) -> None:

#         self._using_default_graph = graph is None

#         self._graph = (
#             evaluation_graph
#             if graph is None
#             else graph
#         )

#         self._llm = llm
#         self._search_client = search_client

#     def evaluate(
#         self,
#         *,
#         url: str,
#         user_prompt: str,
#     ) -> dict[str, Any]:

#         self._validate_input(
#             url=url,
#             user_prompt=user_prompt,
#         )

#         initial_state: dict[str, Any] = {
#             "url": url.strip(),
#             "user_prompt": user_prompt.strip(),
#         }

#         # When a fake graph is injected, keep the service
#         # completely independent of external dependencies.
#         if not self._using_default_graph:

#             result = self._graph.invoke(initial_state)

#             if not isinstance(result, dict):
#                 raise TypeError(
#                     "Evaluation workflow must return a dictionary state."
#                 )

#             return result

#         if self._llm is None:
#             raise RuntimeError(
#                 "LLM is required to run the evaluation workflow."
#             )

#         if self._search_client is None:
#             raise RuntimeError(
#                 "Search client is required to run knowledge validation."
#             )

#         initial_state.update(
#             {
#                 "prompt_alignment_evaluator": (
#                     PromptAlignmentEvaluator(
#                         llm=self._llm
#                     )
#                 ),
#                 "knowledge_validation_evaluator": (
#                     KnowledgeValidationEvaluator(
#                         llm=self._llm,
#                         search_client=self._search_client,
#                     )
#                 ),
#                 "seo_quality_evaluator": (
#                     SEOQualityEvaluator()
#                 ),
#                 "search_quality_evaluator": (
#                     SearchQualityEvaluator(
#                         llm=self._llm
#                     )
#                 ),
#                 "technical_html_evaluator": (
#                     TechnicalHTMLEvaluator()
#                 ),
#             }
#         )

#         result = self._graph.invoke(initial_state)

#         if not isinstance(result, dict):
#             raise TypeError(
#                 "Evaluation workflow must return a dictionary state."
#             )

#         return result

#     @staticmethod
#     def _validate_input(
#         *,
#         url: str,
#         user_prompt: str,
#     ) -> None:

#         if not isinstance(url, str) or not url.strip():
#             raise ValueError(
#                 "URL must be a non-empty string."
#             )

#         if (
#             not isinstance(user_prompt, str)
#             or not user_prompt.strip()
#         ):
#             raise ValueError(
#                 "User prompt must be a non-empty string."
#             )


# def evaluate_webpage(
#     *,
#     url: str,
#     user_prompt: str,
#     llm: Any | None = None,
#     search_client: Any | None = None,
# ) -> dict[str, Any]:

#     service = EvaluationService(
#         llm=llm,
#         search_client=search_client,
#     )

#     return service.evaluate(
#         url=url,
#         user_prompt=user_prompt,
#     )

# # """
# # End-to-end webpage evaluation service.
# # """

# # from __future__ import annotations

# # from typing import Any

# # from evaluator.extractor.fetcher import HTMLFetcher
# # from evaluator.extractor.parser import HTMLParser
# # from evaluator.extractor.content_extractor import ContentExtractor

# # from evaluator.evaluators.prompt_alignment import PromptAlignmentEvaluator
# # from evaluator.evaluators.knowledge_validation import KnowledgeValidationEvaluator
# # from evaluator.evaluators.seo_content_quality import SEOQualityEvaluator
# # from evaluator.evaluators.search_quality import SearchQualityEvaluator
# # from evaluator.evaluators.technical_html import TechnicalHTMLEvaluator

# # from evaluator.graph.workflow import evaluation_graph


# # class EvaluationService:
# #     """
# #     Application-level entry point for the complete
# #     webpage evaluation pipeline.
# #     """

# #     def __init__(
# #         self,
# #         graph: Any | None = None,
# #     ) -> None:

# #         self._graph = graph or evaluation_graph

# #         # Infrastructure dependencies
# #         self._fetcher = HTMLFetcher()
# #         self._parser = HTMLParser()

# #     def evaluate(
# #         self,
# #         *,
# #         url: str,
# #         user_prompt: str,
# #     ) -> dict[str, Any]:
# #         """
# #         Run the complete webpage evaluation.
# #         """

# #         self._validate_input(
# #             url=url,
# #             user_prompt=user_prompt,
# #         )

# #         url = url.strip()
# #         user_prompt = user_prompt.strip()

# #         # ---------------------------------------------------------
# #         # 1. FETCH
# #         # ---------------------------------------------------------

# #         html = self._fetcher.fetch(url)

# #         # ---------------------------------------------------------
# #         # 2. PARSE
# #         # ---------------------------------------------------------

# #         soup = self._parser.parse(html)

# #         # ---------------------------------------------------------
# #         # 3. EXTRACT WEBSITE CONTENT
# #         # ---------------------------------------------------------

# #         website_content = ContentExtractor.extract(
# #             url=url,
# #             soup=soup,
# #         )

# #         # ---------------------------------------------------------
# #         # 4. CREATE EVALUATOR DEPENDENCIES
# #         # ---------------------------------------------------------

# #         prompt_alignment_evaluator = PromptAlignmentEvaluator()
# #         knowledge_validation_evaluator = KnowledgeValidationEvaluator()
# #         seo_quality_evaluator = SEOQualityEvaluator()
# #         search_quality_evaluator = SearchQualityEvaluator()
# #         technical_html_evaluator = TechnicalHTMLEvaluator()

# #         # ---------------------------------------------------------
# #         # 5. INITIAL LANGGRAPH STATE
# #         # ---------------------------------------------------------

# #         initial_state = {
# #             "url": url,
# #             "user_prompt": user_prompt,

# #             "website_content": website_content,

# #             "prompt_alignment_evaluator": (
# #                 prompt_alignment_evaluator
# #             ),

# #             "knowledge_validation_evaluator": (
# #                 knowledge_validation_evaluator
# #             ),

# #             "seo_quality_evaluator": (
# #                 seo_quality_evaluator
# #             ),

# #             "search_quality_evaluator": (
# #                 search_quality_evaluator
# #             ),

# #             "technical_html_evaluator": (
# #                 technical_html_evaluator
# #             ),
# #         }

# #         # ---------------------------------------------------------
# #         # 6. RUN LANGGRAPH
# #         # ---------------------------------------------------------

# #         result = self._graph.invoke(initial_state)

# #         if not isinstance(result, dict):
# #             raise TypeError(
# #                 "Evaluation workflow must return a dictionary state."
# #             )

# #         return result

# #     @staticmethod
# #     def _validate_input(
# #         *,
# #         url: str,
# #         user_prompt: str,
# #     ) -> None:
# #         """
# #         Validate required evaluation inputs.
# #         """

# #         if not isinstance(url, str) or not url.strip():
# #             raise ValueError(
# #                 "URL must be a non-empty string."
# #             )

# #         if not isinstance(user_prompt, str) or not user_prompt.strip():
# #             raise ValueError(
# #                 "User prompt must be a non-empty string."
# #             )


# # def evaluate_webpage(
# #     *,
# #     url: str,
# #     user_prompt: str,
# # ) -> dict[str, Any]:
# #     """
# #     Convenience function.
# #     """

# #     service = EvaluationService()

# #     return service.evaluate(
# #         url=url,
# #         user_prompt=user_prompt,
# #     )