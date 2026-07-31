from pydantic import BaseModel, Field
from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import Issue, Recommendation, SearchQualityResult


class SearchQualityLLMResult(BaseModel):
    """
    Structured response returned by the LLM.

    NOTE:
    Search intent is a description, not a numeric score.
    All other quality dimensions use a 0-100 score.
    """
    # FIX: search_intent is text, not search_intent_score.
    search_intent: str = ""
    score: int = Field(ge=0, le=100)
    helpfulness_score: int = Field(ge=0, le=100)
    completeness_score: int = Field(ge=0, le=100)
    natural_writing_score: int = Field(ge=0, le=100)
    repetition_score: int = Field(ge=0, le=100)
    ai_sounding_score: int = Field(ge=0, le=100)
    content_depth_score: int = Field(ge=0, le=100)
    readability_score: int = Field(ge=0, le=100)
    user_satisfaction_score: int = Field(ge=0, le=100)
    missing_sections: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SearchQualityEvaluator:
    """
    Evaluates webpage content from a search-user perspective.

    This evaluator checks whether a user arriving from search
    is likely to find the page useful, complete, readable,
    natural, and satisfying.

    It does NOT evaluate:
    - Google's actual ranking position
    - technical SEO
    - factual correctness
    - property-card correctness
    - backlinks
    - keyword density
    """

    def __init__(self, llm):
        self.llm = llm

    def evaluate(self, content: WebsiteContent) -> SearchQualityResult:
        result = self._analyze(content)
        severity = self._issue_severity(result.score)

        issues = [Issue(severity=severity, title="Search Quality Issue", description=issue) for issue in result.issues]
        recommendations = [Recommendation(title="Improve Search Quality", description=recommendation) for recommendation in result.recommendations]

        return SearchQualityResult(
            score=result.score,
            search_intent=result.search_intent,
            helpfulness_score=result.helpfulness_score,
            completeness_score=result.completeness_score,
            natural_writing_score=result.natural_writing_score,
            repetition_score=result.repetition_score,
            ai_sounding_score=result.ai_sounding_score,
            content_depth_score=result.content_depth_score,
            readability_score=result.readability_score,
            user_satisfaction_score=result.user_satisfaction_score,
            missing_sections=result.missing_sections,
            issues=issues,
            recommendations=recommendations,
        )

    def _analyze(self, content: WebsiteContent) -> SearchQualityLLMResult:
        structured_llm = self.llm.with_structured_output(SearchQualityLLMResult)
        prompt = self._build_prompt(content)
        return structured_llm.invoke(prompt)

    @staticmethod
    def _build_prompt(content: WebsiteContent) -> str:
        headings = []
        for heading_list in (content.headings.h1, content.headings.h2, content.headings.h3):
            headings.extend(heading_list)

        return f"""
Evaluate the quality of this webpage from the perspective
of a user who discovers the page through a search engine.

The goal is to determine whether the page satisfies the
user's likely information need.

PAGE TITLE:
{content.title}

META DESCRIPTION:
{content.meta_description}

HEADINGS:
{headings}

PAGE CONTENT:
{content.plain_text[:12000]}

Evaluate the following dimensions.

1. SEARCH INTENT

Describe the likely search intent this page is tryiny to satisfy.

Return this as a short text description.

2. HELPFULNESS

Does the page provide genuinely useful information instead of generic filler?

Score from 0 to 100.

3. COMPLETENESS

Does the page cover the important information a user would reasonably expect?

Score from 0 to 100.

4. NATURAL WRITING

Does the content read naturally and clearly for humans?

Score from 0 to 100.

5. REPETITION

Does the page avoid unnecessary repetition?

100 = very little unnecessary repetition.
0 = extremely repetitive.

6. AI-SOUNDING CONTENT

Does the content feel generic, formulaic, repetitive, or obviously machine-generated?

100 = natural and original sounding.
0 = strongly AI-like.

7. CONTENT DEPTH

Does the page provide meaningful detail instead of shallow generic information?

Score from 0 to 100.

8. MISSING SECTIONS

Identify important sections that are missing and would reasonably help the user.

Score completeness from 0 to 100 through the completeness_score field.

9. READABILITY

Is the content easy to understand, scan, and consume?

Score from 0 to 100.

10. USER SATISFACTION

Would a typical search visitor likely feel that their
information need was satisfied?

Score from 0 to 100.

OVERALL SCORE:

Calculate an overall quality score from 0 to 100.

90-100 = excellent
80-89 = very good
70-79 = good
60-69 = acceptable
40-59 = poor
0-39 = very poor

IMPORTANT:

Do NOT evaluate:

- technical SEO
- HTML quality
- keyword density
- keyword placement
- backlinks
- domain authority
- Core Web Vitals
- schema markup
- image ALT attributes
- Google's exact ranking algorithm
- factual correctness
- property-card correctness

Do not invent facts about the webpage.

Return concrete issues and concrete recommendations.

Return the result using the required structured schema.
"""

    @staticmethod
    def _issue_severity(score: int) -> str:
        if score < 40:
            return "High"
        if score < 70:
            return "Medium"
        return "Low"