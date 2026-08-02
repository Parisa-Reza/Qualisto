from django.urls import path

from .views import evaluation_page, evaluate_website


urlpatterns = [
    path("", evaluation_page, name="evaluation-page"),

    # API endpoint used by evaluation.js
    path("api/evaluate/", evaluate_website, name="evaluate-website"),
]