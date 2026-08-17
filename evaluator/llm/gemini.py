from google import genai

from django.conf import settings


def create_gemini_client():
    """Create the Gemini client used for image validation."""

    api_key = getattr(settings, "GEMINI_API_KEY", None)

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not configured."
        )

    return genai.Client(api_key=api_key)