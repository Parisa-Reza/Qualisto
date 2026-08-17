import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from google import genai

from evaluator.e2e_service.evaluator import EvaluationService
from evaluator.llm.ollama import create_ollama_model
from evaluator.tavily_search.tavily import TavilySearchClient


logger = logging.getLogger(__name__)


def evaluation_page(request):
    """Render the webpage evaluation page."""

    return render(
        request,
        "evaluator/evaluation.html",
    )


@require_POST
def evaluate_website(request):
    """
    Evaluate a webpage using the complete evaluation workflow.

    The workflow uses:
        - Ollama for text/knowledge-related LLM evaluation.
        - Tavily for external search evidence.
        - Gemini for multimodal hero-image validation.

    Returns:
        JsonResponse containing the evaluation report or an error.
    """

    logger.info("Received evaluation request.")

    prompt = request.POST.get(
        "prompt",
        "",
    ).strip()

    url = request.POST.get(
        "url",
        "",
    ).strip()

    logger.info(
        "Evaluation request received | url=%s | prompt_length=%d",
        url,
        len(prompt),
    )

    # --------------------------------------------------------------
    # INPUT VALIDATION
    # --------------------------------------------------------------

    if not prompt:
        logger.warning(
            "Evaluation rejected: prompt missing."
        )

        return JsonResponse(
            {
                "success": False,
                "error": "User prompt is required.",
            },
            status=400,
        )

    if not url:
        logger.warning(
            "Evaluation rejected: URL missing."
        )

        return JsonResponse(
            {
                "success": False,
                "error": "URL is required.",
            },
            status=400,
        )

    try:
        # ----------------------------------------------------------
        # CREATE OLLAMA LLM
        # ----------------------------------------------------------

        logger.info(
            "Creating local Ollama LLM."
        )

        llm = create_ollama_model()

        logger.info(
            "Local Ollama LLM created | model=%s",
            getattr(
                llm,
                "model",
                "unknown",
            ),
        )

        # ----------------------------------------------------------
        # CREATE TAVILY CLIENT
        # ----------------------------------------------------------

        logger.info(
            "Creating Tavily search client."
        )

        search_client = TavilySearchClient()

        # ----------------------------------------------------------
        # CREATE GEMINI CLIENT
        # ----------------------------------------------------------
        #
        # Gemini is required by KnowledgeValidationEvaluator for
        # hero-image geographic validation.
        #
        # IMPORTANT:
        # This client MUST be passed into EvaluationService.
        # Otherwise EvaluationService.evaluate() receives:
        #
        #     gemini_client=None
        #
        # and raises:
        #
        #     RuntimeError:
        #     Gemini client is required for hero image validation.
        # ----------------------------------------------------------

        gemini_api_key = getattr(
            settings,
            "GEMINI_API_KEY",
            "",
        )

        if not gemini_api_key:
            logger.error(
                "GEMINI_API_KEY is missing from Django settings."
            )

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "Gemini API key is not configured. "
                        "Set GEMINI_API_KEY in Django settings."
                    ),
                },
                status=500,
            )

        logger.info(
            "Creating Gemini client for hero-image validation."
        )

        gemini_client = genai.Client(
            api_key=gemini_api_key,
        )

        logger.info(
            "Gemini client created successfully."
        )

        # ----------------------------------------------------------
        # CREATE EVALUATION SERVICE
        # ----------------------------------------------------------

        logger.info(
            "Creating EvaluationService."
        )

        service = EvaluationService(
            llm=llm,
            search_client=search_client,
            gemini_client=gemini_client,
        )

        logger.info(
            "EvaluationService created | "
            "gemini_enabled=%s",
            bool(gemini_client),
        )

        # ----------------------------------------------------------
        # RUN EVALUATION
        # ----------------------------------------------------------

        logger.info(
            "Starting website evaluation | url=%s",
            url,
        )

        result = service.evaluate(
            url=url,
            user_prompt=prompt,
        )

        logger.info(
            "Website evaluation returned successfully."
        )

        # ----------------------------------------------------------
        # BUILD RESPONSE
        # ----------------------------------------------------------

        report = result["evaluation_report"]

        logger.info(
            "Final evaluation score=%s",
            report.final_score,
        )

        return JsonResponse(
            {
                "success": True,

                "report": {
                    "final_score": report.final_score,

                    "prompt_alignment": (
                        report.prompt_alignment.score
                    ),

                    "knowledge_validation": (
                        report.knowledge_validation.score
                    ),

                    "seo_quality": (
                        report.seo_quality.score
                    ),

                    "search_quality": (
                        report.search_quality.score
                    ),

                    "technical_html": (
                        report.technical_html.score
                    ),

                    "issues": [
                        {
                            "severity": issue.severity,
                            "title": issue.title,
                            "description": issue.description,
                        }
                        for issue in report.issues
                    ],

                    "recommendations": [
                        {
                            "title": recommendation.title,
                            "description": recommendation.description,
                        }
                        for recommendation in report.recommendations
                    ],
                },
            }
        )

    except Exception as exc:
        logger.exception(
            "Website evaluation failed."
        )

        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )