import logging
import os
from typing import Any, get_args, get_origin
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


def create_ollama_model():

    model = os.getenv(
        "OLLAMA_MODEL",
        "qwen3:1.7b",
    )

    base_url = os.getenv(
        "OLLAMA_BASE_URL",
        "http://127.0.0.1:11434",
    )

    if not isinstance(base_url, str):
        base_url = "http://127.0.0.1:11434"
    else:
        base_url = base_url.strip()

    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        logger.warning(
            "Invalid Ollama base URL %r; falling back to http://127.0.0.1:11434",
            base_url,
        )
        base_url = "http://127.0.0.1:11434"

    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        os.environ.pop("ALL_PROXY", None)
        os.environ.pop("all_proxy", None)

    logger.info(
        "Creating Ollama model | model=%s | base_url=%s",
        model,
        base_url,
    )

    try:
        from langchain_ollama import ChatOllama
    except Exception as exc:
        logger.exception(
            "Failed to import langchain_ollama; using fallback stub LLM."
        )

        fallback_model = "llama3.2:3b" if model in {"qwen3:1.7b"} else model

        class StubLLM:
            def __init__(self, model_name: str):
                self.model = model_name
                self.temperature = 0

            def with_structured_output(self, schema):
                class _Result:
                    def invoke(self, prompt):
                        annotations = getattr(schema, "__annotations__", {})
                        values = {}

                        for field_name, field_type in annotations.items():
                            if field_name == "score":
                                values[field_name] = 0
                            elif field_name == "status":
                                values[field_name] = "uncertain"
                            elif field_name == "reason":
                                values[field_name] = "Fallback stub response because the Ollama client is unavailable."
                            elif field_name.endswith("_score"):
                                values[field_name] = 0
                            elif field_name in {"issues", "suggestions", "missing_requirements", "off_topic_sections", "missing_sections", "recommendations"}:
                                values[field_name] = []
                            elif field_name in {"verified_claims", "unsupported_claims", "uncertain_claims"}:
                                values[field_name] = []
                            elif field_name in {"search_intent"}:
                                values[field_name] = "Fallback stub response."
                            elif field_name in {"helpfulness_score", "completeness_score", "natural_writing_score", "repetition_score", "ai_sounding_score", "content_depth_score", "readability_score", "user_satisfaction_score"}:
                                values[field_name] = 0
                            else:
                                values[field_name] = None

                        return schema(**values)

                return _Result()

        return StubLLM(fallback_model)

    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
    )

    logger.info(
        "Ollama model created successfully."
    )

    return llm






# from langchain_ollama import ChatOllama


# def create_ollama_model():
#     return ChatOllama(
#         model="qwen3:1.7b",
#         base_url="http://127.0.0.1:11434",
#         temperature=0,
#     )




# import os

# from dotenv import load_dotenv
# from langchain_google_genai import ChatGoogleGenerativeAI

# load_dotenv()


# def create_gemini_model():
#     api_key = os.getenv("GEMINI_API_KEY")

#     if not api_key:
#         raise ValueError("GEMINI_API_KEY is not configured.")

#     return ChatGoogleGenerativeAI(
#         model="gemini-3.1-flash-lite",
#         temperature=0,
#         google_api_key=api_key,
#     )