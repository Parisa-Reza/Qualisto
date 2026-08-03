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
    missing_requirements: list[str] = Field(default_factory=list)
    off_topic_sections: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


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

        logger.debug(
            "Prompt alignment input | prompt_length=%d | content_length=%d",
            len(prompt),
            len(content.plain_text),
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
                severity="Medium",
                title="Prompt Alignment Issue",
                description=issue,
            )
            for issue in result.issues
        ]

        recommendations = [
            Recommendation(
                title="Improve Prompt Alignment",
                description=suggestion,
            )
            for suggestion in result.suggestions
        ]

        logger.info(
            "Prompt alignment evaluation completed | score=%d | issues=%d | recommendations=%d",
            result.score,
            len(issues),
            len(recommendations),
        )

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

        try:

            result = structured_llm.invoke(
                self._build_prompt(
                    prompt,
                    content,
                )
            )

        except Exception:

            logger.exception(
                "Prompt alignment LLM call failed."
            )

            raise

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
Evaluate whether this webpage satisfies the user's original request.

USER REQUEST:
{prompt}

WEBPAGE TITLE:
{content.title}

HEADINGS:
{content.headings}

CONTENT:
{content.plain_text}

Check only:

1. Requested topics are covered.
2. Important requirements are not missing.
3. The page remains focused on the requested subject.
4. Identify clearly off-topic content.
5. Give an overall satisfaction score from 0 to 100.

Do NOT evaluate:
- HTML
- technical SEO
- keyword density
- keyword placement
- links
- images
- ALT attributes
- title length
- meta description length

Return the result using the required structured schema.
"""






# from pydantic import BaseModel, Field
# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import Issue, PromptAlignmentResult, Recommendation


# class PromptAlignmentLLMResult(BaseModel):
#     score: int = Field(ge=0, le=100)
#     missing_requirements: list[str] = Field(default_factory=list)
#     off_topic_sections: list[str] = Field(default_factory=list)
#     issues: list[str] = Field(default_factory=list)
#     suggestions: list[str] = Field(default_factory=list)


# class PromptAlignmentEvaluator:
#     def __init__(self, llm):
#         self.llm = llm

#     def evaluate(self, prompt: str, content: WebsiteContent) -> PromptAlignmentResult:
#         result = self._analyze(prompt, content)
#         issues = [Issue(severity="Medium", title="Prompt Alignment Issue", description=issue) for issue in result.issues]
#         recommendations = [Recommendation(title="Improve Prompt Alignment", description=suggestion) for suggestion in result.suggestions]
#         return PromptAlignmentResult(score=result.score, issues=issues, recommendations=recommendations, missing_requirements=result.missing_requirements, off_topic_sections=result.off_topic_sections)

#     def _analyze(self, prompt: str, content: WebsiteContent) -> PromptAlignmentLLMResult:
#         structured_llm = self.llm.with_structured_output(PromptAlignmentLLMResult)
#         return structured_llm.invoke(self._build_prompt(prompt, content))

#     @staticmethod
#     def _build_prompt(prompt: str, content: WebsiteContent) -> str:
#         return f"""
# Evaluate whether this webpage satisfies the user's original request.

# USER REQUEST:
# {prompt}

# WEBPAGE TITLE:
# {content.title}

# HEADINGS:
# {content.headings}

# CONTENT:
# {content.plain_text}

# Check only:

# 1. Requested topics are covered.
# 2. Important requirements are not missing.
# 3. The page remains focused on the requested subject.
# 4. Identify clearly off-topic content.
# 5. Give an overall satisfaction score from 0 to 100.

# Do NOT evaluate:
# - HTML
# - technical SEO
# - keyword density
# - keyword placement
# - links
# - images
# - ALT attributes
# - title length
# - meta description length

# Return the result using the required structured schema.
# """