import logging

from pydantic import BaseModel, Field

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import (
    Issue,
    Recommendation,
    SearchQualityResult,
)


logger = logging.getLogger(__name__)


class SearchQualityLLMResult(BaseModel):

    search_intent: str = ""

    score: int = Field(
        ge=0,
        le=100,
    )

    helpfulness_score: int = Field(
        ge=0,
        le=100,
    )

    completeness_score: int = Field(
        ge=0,
        le=100,
    )

    natural_writing_score: int = Field(
        ge=0,
        le=100,
    )

    repetition_score: int = Field(
        ge=0,
        le=100,
    )

    ai_sounding_score: int = Field(
        ge=0,
        le=100,
    )

    content_depth_score: int = Field(
        ge=0,
        le=100,
    )

    readability_score: int = Field(
        ge=0,
        le=100,
    )

    user_satisfaction_score: int = Field(
        ge=0,
        le=100,
    )

    missing_sections: list[str] = Field(
        default_factory=list
    )

    issues: list[str] = Field(
        default_factory=list
    )

    recommendations: list[str] = Field(
        default_factory=list
    )


class SearchQualityEvaluator:

    def __init__(self, llm):

        self.llm = llm

        logger.info(
            "SearchQualityEvaluator initialized | llm=%s",
            type(llm).__name__,
        )

    def evaluate(
        self,
        content: WebsiteContent,
    ) -> SearchQualityResult:

        logger.info(
            "Search quality evaluation started."
        )

        result = self._analyze(content)

        severity = self._issue_severity(
            result.score
        )

        issues = [
            Issue(
                severity=severity,
                title="Search Quality",
                description=issue,
            )
            for issue in result.issues
        ]

        recommendations = [
            Recommendation(
                title="Improve Search Quality",
                description=recommendation,
            )
            for recommendation in result.recommendations
        ]

        logger.info(
            "Search quality evaluation completed | score=%d | issues=%d | recommendations=%d",
            result.score,
            len(issues),
            len(recommendations),
        )

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

    def _analyze(
        self,
        content: WebsiteContent,
    ) -> SearchQualityLLMResult:

        logger.info(
            "Calling LLM for search quality evaluation."
        )

        structured_llm = self.llm.with_structured_output(
            SearchQualityLLMResult
        )

        result = structured_llm.invoke(
            self._build_prompt(content)
        )

        logger.info(
            "Search quality LLM call successful."
        )

        return result

    @staticmethod
    def _build_prompt(
        content: WebsiteContent,
    ) -> str:

        headings = []

        for heading_list in (
            content.headings.h1,
            content.headings.h2,
            content.headings.h3,
        ):
            headings.extend(
                heading_list
            )

        return f"""
You are evaluating an AI-generated travel webpage from the perspective
of a real human visitor who found the page through search.

Your ONLY responsibility is SEARCH / CONTENT QUALITY.

================ PAGE TITLE ================
{content.title}

================ META DESCRIPTION ================
{content.meta_description}

================ HEADINGS ================
{headings}

================ PAGE CONTENT ================
{content.plain_text[:16000]}

================ EVALUATE ================

1. Search intent

Identify what a visitor is likely looking for.

2. Helpfulness

Does the page provide useful information instead of generic filler?

3. Completeness

Does it cover the information a visitor reasonably needs?

4. Natural writing

Does it sound natural and human-readable?

5. Repetition

Does the page unnecessarily repeat the same information?

100 = minimal unnecessary repetition.
0 = extremely repetitive.

6. AI-sounding content

Does the content sound formulaic, generic, repetitive, or obviously
machine-generated?

100 = natural human-like writing.
0 = strongly AI-like.

7. Content depth

Does the page provide meaningful details?

8. Readability

Can a visitor easily scan and understand the page?

9. User satisfaction

Would the visitor likely feel that their search intent was satisfied?

10. Missing sections

Identify useful sections that are actually missing.

================ ISSUE RULES ================

Only report concrete problems.

Every issue MUST explain WHERE the problem occurs.

Examples:

"Under 'Things to Do', the descriptions repeat the same generic
information about sightseeing without providing distinct details."

"The 'Where to Stay' section is only two sentences long and does not
give visitors enough information to choose an area."

Do NOT produce generic statements such as:

"The content could be improved."

"The page may confuse users."

"The website should be better."

================ RECOMMENDATION RULES ================

Every recommendation must provide an actionable solution.

It must explain:

1. where the change is needed
2. what should be changed
3. what kind of content should be added/replaced

Example:

"Expand the 'Where to Stay' section with 3-5 distinct neighborhood
options and explain what type of traveler each area suits."

================ DO NOT EVALUATE ================

Do NOT evaluate:

- HTML
- technical SEO
- keyword density
- keyword placement
- backlinks
- domain authority
- Core Web Vitals
- schema markup
- image ALT
- factual correctness
- property/card factual validation

Those are handled by other evaluators.

================ SCORING ================

90-100 = excellent
80-89 = very good
70-79 = good
60-69 = acceptable
40-59 = poor
0-39 = very poor

The score must reflect the actual content.

If the content is good, give it a good score.

Do not lower the score simply because the page is AI-generated.

Return concrete issues and recommendations only.

Return the required structured output.
"""

    @staticmethod
    def _issue_severity(
        score: int,
    ) -> str:

        if score < 40:
            return "High"

        if score < 70:
            return "Medium"

        return "Low"

