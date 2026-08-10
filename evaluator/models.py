from django.db import models


class Evaluation(models.Model):
    url = models.URLField()
    prompt = models.TextField(blank=True)

    overall_score = models.IntegerField(default=0)

    prompt_alignment_score = models.IntegerField(default=0)
    knowledge_validation_score = models.IntegerField(default=0)
    seo_score = models.IntegerField(default=0)
    search_quality_score = models.IntegerField(default=0)
    technical_html_score = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.url} - {self.overall_score}"