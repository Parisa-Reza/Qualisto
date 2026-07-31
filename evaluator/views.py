from django.shortcuts import render

from .extractor.fetcher import HTMLFetcher
from .extractor.parser import HTMLParser
from .extractor.content_extractor import ContentExtractor


def home(request):

    context = {}

    if request.method == "POST":

        user_prompt = request.POST.get("user_prompt", "").strip()
        website_url = request.POST.get("website_url", "").strip()

        context["user_prompt"] = user_prompt
        context["website_url"] = website_url

        try:

            html = HTMLFetcher.fetch(website_url)

            soup = HTMLParser.parse(html)

            website_content = ContentExtractor.extract(
                website_url,
                soup,
            )

            context["content"] = website_content

        except Exception as e:

            context["error"] = str(e)

    return render(
        request,
        "evaluator/home.html",
        context,
    )