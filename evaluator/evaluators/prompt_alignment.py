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
You are evaluating whether an AI-generated webpage follows a user's
explicit website request.

Your ONLY responsibility is PROMPT ALIGNMENT.

The USER PROMPT is the ONLY source of truth for what the webpage was
supposed to be about.

The webpage content is evidence. Do not use the webpage title,
headings, or content to redefine the user's requested destination,
topic, audience, or purpose.

================ USER REQUEST ================
{prompt}

================ WEBPAGE TITLE ================
{content.title}

================ HEADINGS ================
{content.headings}

================ WEBPAGE CONTENT ================
{content.plain_text.strip()}

================ WHAT TO CHECK ================
Determine whether the COMPLETE webpage follows the USER REQUEST.

You MUST inspect the entire webpage text, including content appearing
at the very end of the webpage.

Do NOT stop after reading the beginning of the webpage.

Check ALL of the following:

1. Destination/location alignment.

2. Requested page topic.

3. Requested sections or information.

4. Requested audience or purpose.

5. Important explicit requirements in the USER REQUEST.

6. Clearly unrelated sections or content.

7. Contradictions between the requested destination/topic and the
   webpage content.

============================================================
DESTINATION / LOCATION RULE
============================================================

For travel webpages, destination mismatch is a major prompt-alignment
problem.

If the USER REQUEST asks for a webpage about one destination, content
about a different destination is off-topic unless the USER REQUEST
explicitly asks for comparison, nearby destinations, surrounding
areas, excursions, or another reason that makes the second destination
relevant.

Example:

USER REQUEST:
"Create a travel guide for New York City."

WEBPAGE:
"New York City Travel Guide"

Later:

"Hammamet Travel Guide"

This is an OFF-TOPIC section.

You MUST report it because Hammamet is a different destination from
New York City.

Do not excuse unrelated content merely because the rest of the page
is relevant.

============================================================
IMPORTANT EVIDENCE RULE
============================================================

Only report an issue when there is actual evidence in the webpage.

However, when explicit evidence exists, you MUST report it.

Do not say:

"The page may contain unrelated content."

Instead identify the actual content.

Good:

"The final 'Hammamet' section discusses Hammamet, Tunisia, even
though the user requested a New York City travel guide."

Bad:

"The page contains potentially unrelated destinations."

============================================================
SECTION-BY-SECTION CHECK
============================================================

Treat headings and the text following them as separate webpage
sections.

For every identifiable section, determine:

- What is this section about?
- What destination does it discuss, if any?
- Is that destination consistent with the USER REQUEST?
- Does the section satisfy an explicit requirement?
- Is the section unrelated to the requested topic?

Pay particular attention to sections near the END of the webpage.

============================================================
DO NOT EVALUATE
============================================================

Do NOT evaluate:

- SEO
- HTML
- meta tags
- keyword density
- image ALT text
- links
- factual correctness
- search ranking
- writing quality
- grammar
- visual design

These belong to other evaluation modules.

============================================================
DO NOT INVENT REQUIREMENTS
============================================================

Do not penalize the webpage for requirements that do not appear in
the USER REQUEST.

Do not create generic issues.

Do not infer that something is required merely because it would be
useful for a travel webpage.

============================================================
ISSUE REQUIREMENTS
============================================================

Every issue MUST contain:

1. The actual problem.
2. The location of the problem on the webpage.
3. Evidence from the webpage.
4. Why it conflicts with the USER REQUEST.

For example:

"The final 'Hammamet' section discusses Hammamet, Tunisia, while the
USER REQUEST is for a New York City travel guide. This section is
therefore unrelated to the requested destination."

Do NOT produce vague issues such as:

"The content may confuse users."

============================================================
RECOMMENDATION REQUIREMENTS
============================================================

Every recommendation MUST explain:

1. What should be changed.
2. Where it should be changed.
3. What should replace the problematic content.

Example:

"Remove the final Hammamet section and replace it with information
about a New York City attraction, neighborhood, restaurant, or other
content explicitly requested by the user."

============================================================
SCORING
============================================================

100:
The webpage fully follows the USER REQUEST.

80-99:
Mostly aligned with only minor omissions or minor irrelevant content.

60-79:
Partially aligned; important explicit requirements are missing or
there is meaningful off-topic content.

40-59:
Several important explicit requirements are missing or there is
significant off-topic content.

0-39:
The webpage substantially fails to follow the USER REQUEST.

The score MUST reflect the actual evidence.

If there are no meaningful alignment problems:

- issues MUST be []
- suggestions MUST be []

Do not manufacture issues just to lower the score.

============================================================
FINAL CHECK
============================================================

Before returning the result, perform a final pass over the COMPLETE
WEBPAGE TEXT.

Specifically verify that you did not miss an unrelated destination
or topic appearing near the end of the page.

Return ONLY the required structured output.
"""

    @staticmethod
    def _issue_severity(score: int) -> str:

        if score < 40:
            return "High"

        if score < 70:
            return "Medium"

        return "Low"

