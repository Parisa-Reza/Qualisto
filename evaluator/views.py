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
    return render(request, "evaluator/evaluation.html")

def _serialize_module(module):
    """Convert one evaluator result into a JSON-serializable structure."""
    return {
        "score": module.score,
        "issues": [
            {
                "severity": issue.severity,
                "title": issue.title,
                "description": issue.description,
            }
            for issue in module.issues
        ],
        "recommendations": [
            {
                "title": recommendation.title,
                "description": recommendation.description,
            }
            for recommendation in module.recommendations
        ],
    }

@require_POST
def evaluate_website(request):
    """
    Evaluate one webpage and return module-wise evaluation results.
    The five modules are:
        1. Prompt Alignment
        2. Knowledge Validation
        3. Search Quality
        4. Technical HTML
        5. SEO Content Quality
    """
    logger.info("Received evaluation request.")
    prompt = request.POST.get("prompt", "").strip()
    url = request.POST.get("url", "").strip()
    logger.info("Evaluation request received | url=%s | prompt_length=%d", url, len(prompt))

    if not prompt:
        return JsonResponse({"success": False, "error": "User prompt is required."}, status=400)

    if not url:
        return JsonResponse({"success": False, "error": "URL is required."}, status=400)

    try:
        logger.info("Creating local Ollama LLM.")
        llm = create_ollama_model()
        logger.info("Local Ollama LLM created | model=%s", getattr(llm, "model", "unknown"))

        logger.info("Creating Tavily search client.")
        search_client = TavilySearchClient()

        gemini_api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not gemini_api_key:
            logger.error("GEMINI_API_KEY is missing.")
            return JsonResponse({"success": False, "error": "Gemini API key is not configured."}, status=500)

        logger.info("Creating Gemini client.")
        gemini_client = genai.Client(api_key=gemini_api_key)

        service = EvaluationService(
            llm=llm,
            search_client=search_client,
            gemini_client=gemini_client,
        )

        logger.info("Starting website evaluation | url=%s", url)
        result = service.evaluate(url=url, user_prompt=prompt)
        report = result["evaluation_report"]

        modules = {
            "prompt_alignment": {
                "name": "Prompt Alignment",
                **_serialize_module(report.prompt_alignment),
            },
            "knowledge_validation": {
                "name": "Knowledge Validation",
                **_serialize_module(report.knowledge_validation),
            },
            "search_quality": {
                "name": "Search Quality",
                **_serialize_module(report.search_quality),
            },
            "technical_html": {
                "name": "Technical HTML",
                **_serialize_module(report.technical_html),
            },
            "seo_quality": {
                "name": "SEO Content Quality",
                **_serialize_module(report.seo_quality),
            },
        }

        logger.info("Final evaluation score=%s", report.final_score)

        return JsonResponse(
            {
                "success": True,
                "report": {
                    "url": url,
                    "user_prompt": prompt,
                    "final_score": report.final_score,
                    "scores": {
                        key: module["score"]
                        for key, module in modules.items()
                    },
                    "modules": modules,
                },
            }
        )

    except Exception as exc:
        logger.exception("Website evaluation failed.")
        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )
