import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from evaluator.e2e_service.evaluator import EvaluationService
from evaluator.llm.ollama import create_ollama_model
from evaluator.tavily_search.tavily import TavilySearchClient


logger = logging.getLogger(__name__)


def evaluation_page(request):

    return render(
        request,
        "evaluator/evaluation.html",
    )


@require_POST
def evaluate_website(request):

    logger.info(
        "Received evaluation request."
    )

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

        logger.info(
            "Creating Tavily search client."
        )

        search_client = TavilySearchClient()

        logger.info(
            "Creating EvaluationService."
        )

        service = EvaluationService(
            llm=llm,
            search_client=search_client,
        )

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



# from django.http import JsonResponse
# from django.shortcuts import render
# from django.views.decorators.http import require_POST

# # from langchain_google_genai import ChatGoogleGenerativeAI
# from evaluator.llm.ollama import create_ollama_model
# from evaluator.e2e_service.evaluator import EvaluationService
# from evaluator.tavily_search.tavily import TavilySearchClient


# def evaluation_page(request):
#     return render(
#         request,
#         "evaluator/evaluation.html",
#     )


# @require_POST
# def evaluate_website(request):

#     prompt = request.POST.get(
#         "prompt",
#         "",
#     ).strip()

#     url = request.POST.get(
#         "url",
#         "",
#     ).strip()

#     if not prompt:
#         return JsonResponse(
#             {
#                 "success": False,
#                 "error": "User prompt is required.",
#             },
#             status=400,
#         )

#     if not url:
#         return JsonResponse(
#             {
#                 "success": False,
#                 "error": "URL is required.",
#             },
#             status=400,
#         )

#     try:

#         # llm = ChatGoogleGenerativeAI(
#         #     model="gemini-3.1-flash-lite",
#         #     temperature=0,
#         # )
#         llm = create_ollama_model()

#         search_client = TavilySearchClient()

#         service = EvaluationService(
#             llm=llm,
#             search_client=search_client,
#         )

#         result = service.evaluate(
#             url=url,
#             user_prompt=prompt,
#         )

#         report = result["evaluation_report"]

#         return JsonResponse(
#             {
#                 "success": True,

#                 "report": {
#                     "final_score": report.final_score,

#                     "prompt_alignment": (
#                         report.prompt_alignment.score
#                     ),

#                     "knowledge_validation": (
#                         report.knowledge_validation.score
#                     ),

#                     "seo_quality": (
#                         report.seo_quality.score
#                     ),

#                     "search_quality": (
#                         report.search_quality.score
#                     ),

#                     "technical_html": (
#                         report.technical_html.score
#                     ),

#                     "issues": [
#                         {
#                             "severity": issue.severity,
#                             "title": issue.title,
#                             "description": issue.description,
#                         }
#                         for issue in report.issues
#                     ],

#                     "recommendations": [
#                         {
#                             "title": recommendation.title,
#                             "description": recommendation.description,
#                         }
#                         for recommendation in report.recommendations
#                     ],
#                 },
#             }
#         )

#     except Exception as exc:

#         return JsonResponse(
#             {
#                 "success": False,
#                 "error": str(exc),
#             },
#             status=500,
#         )
