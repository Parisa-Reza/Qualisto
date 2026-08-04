import logging

from pydantic import BaseModel, Field

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import (
    Issue,
    PromptAlignmentResult,
    Recommendation,
)


logger = logging.getLogger(__name__)


class PromptAlignmentLLMResult(BaseModel):
    score: int = Field(ge=0, le=100)

    missing_requirements: list[str] = Field(
        default_factory=list
    )

    off_topic_sections: list[str] = Field(
        default_factory=list
    )

    issues: list[str] = Field(
        default_factory=list
    )

    suggestions: list[str] = Field(
        default_factory=list
    )


class PromptAlignmentEvaluator:

    def __init__(self, llm):
        self.llm = llm

        logger.info(
            "PromptAlignmentEvaluator initialized | llm=%s",
            type(llm).__name__,
        )

    def evaluate(
        self,
        prompt: str,
        content: WebsiteContent,
    ) -> PromptAlignmentResult:

        logger.info(
            "Prompt alignment evaluation started."
        )

        result = self._analyze(
            prompt,
            content,
        )

        logger.info(
            "Prompt alignment LLM analysis completed | score=%d",
            result.score,
        )

        issues = [
            Issue(
                severity=self._issue_severity(result.score),
                title="Prompt Alignment",
                description=issue,
            )
            for issue in result.issues
        ]

        recommendations = [
            Recommendation(
                title="Fix Prompt Alignment",
                description=suggestion,
            )
            for suggestion in result.suggestions
        ]

        return PromptAlignmentResult(
            score=result.score,
            issues=issues,
            recommendations=recommendations,
            missing_requirements=result.missing_requirements,
            off_topic_sections=result.off_topic_sections,
        )

    def _analyze(
        self,
        prompt: str,
        content: WebsiteContent,
    ) -> PromptAlignmentLLMResult:

        logger.info(
            "Calling LLM for prompt alignment."
        )

        structured_llm = self.llm.with_structured_output(
            PromptAlignmentLLMResult
        )

        result = structured_llm.invoke(
            self._build_prompt(
                prompt,
                content,
            )
        )

        logger.info(
            "Prompt alignment LLM call successful."
        )

        return result

    @staticmethod
    def _build_prompt(
        prompt: str,
        content: WebsiteContent,
    ) -> str:

        return f"""
You are evaluating an AI-generated travel webpage.

Your ONLY responsibility is PROMPT ALIGNMENT.

Determine whether the webpage actually follows the user's requested
website/page requirements.

================ USER REQUEST ================
{prompt}

================ WEBPAGE TITLE ================
{content.title}

================ HEADINGS ================
{content.headings}

================ WEBPAGE CONTENT ================
{content.plain_text[:16000]}

================ WHAT TO CHECK ================

Check:

1. Destination/location alignment.
2. Requested page topic.
3. Requested sections or information.
4. Required audience/purpose.
5. Important requirements from the user's prompt.
6. Content that is clearly unrelated to the requested destination/topic.
7. Contradictions between the requested destination and the webpage content.

For a travel website, destination mismatch is IMPORTANT.

Example:

User requests:
"Create a travel guide for London."

Webpage contains:
"Best restaurants in New York."

That is an OFF-TOPIC issue.

================ IMPORTANT RULES ================

Do NOT evaluate:

- SEO
- HTML
- meta tags
- keyword density
- image ALT
- links
- factual correctness
- search ranking
- writing quality

Do NOT invent requirements that are not present in the user request.

Do NOT create generic issues.

Only report an issue when the webpage content provides evidence for it.

Every issue MUST identify WHERE the problem occurs.

Use wording such as:

"Under the 'Restaurants' section, the page discusses New York
restaurants even though the requested destination is London."

Do NOT write vague statements such as:

"The content may confuse users."

Every recommendation MUST explain:

1. what should be changed
2. where it should be changed
3. what should replace/fix the problematic content

Example:

"Replace the New York restaurant section with restaurants located
in London."

================ SCORING ================

100:
The webpage fully follows the user's request.

80-99:
Mostly aligned with only minor omissions.

60-79:
Partially aligned; important requirements are missing.

40-59:
Several important requirements are missing or there is significant
off-topic content.

0-39:
The webpage substantially fails to follow the user's request.

The score MUST reflect actual alignment.

If there are no meaningful alignment problems, return an empty
issues list and an empty suggestions list.

Return the required structured output.
"""

    @staticmethod
    def _issue_severity(score: int) -> str:

        if score < 40:
            return "High"

        if score < 70:
            return "Medium"

        return "Low"

