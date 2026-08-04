import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import (
    Issue,
    KnowledgeValidationResult,
    Recommendation,
)

logger = logging.getLogger(__name__)


class ClaimValidationLLMResult(BaseModel):
    status: str = Field(
        description="verified, unsupported, or uncertain"
    )
    claim: str = ""
    evidence: str = ""
    location: str = ""
    explanation: str = ""


class PropertyCardValidationLLMResult(BaseModel):
    status: str = Field(
        description="valid or context_mismatch"
    )
    reason: str = ""


class KnowledgeValidationLLMResult(BaseModel):
    score: int = Field(ge=0, le=100)
    verified_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class KnowledgeValidationEvaluator:

    def __init__(
        self,
        llm,
        search_client,
        max_workers: int = 8,
    ):
        self.llm = llm
        self.search_client = search_client
        self.max_workers = max_workers

        logger.info(
            "KnowledgeValidationEvaluator initialized | "
            "llm=%s | search_client=%s | max_workers=%d",
            type(llm).__name__,
            type(search_client).__name__,
            max_workers,
        )

    def evaluate(
        self,
        content: WebsiteContent,
    ) -> KnowledgeValidationResult:
        logger.info("Knowledge validation evaluation started.")

        result = self._analyze(content)

        issues = [
            Issue(
                severity=self._issue_severity(result.score),
                title="Knowledge Validation",
                description=issue,
            )
            for issue in result.issues
        ]

        recommendations = [
            Recommendation(
                title="Fix Knowledge Issue",
                description=recommendation,
            )
            for recommendation in result.recommendations
        ]

        card_issues, card_recommendations = (
            self._validate_property_cards(content)
        )

        issues.extend(card_issues)
        recommendations.extend(card_recommendations)

        score = max(
            0,
            result.score - len(card_issues) * 15,
        )

        logger.info(
            "Knowledge validation completed | "
            "base_score=%d | card_issues=%d | final_score=%d",
            result.score,
            len(card_issues),
            score,
        )

        return KnowledgeValidationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
            verified_claims=result.verified_claims,
            unsupported_claims=result.unsupported_claims,
            uncertain_claims=result.uncertain_claims,
        )

    # ============================================================
    # GENERAL KNOWLEDGE VALIDATION
    # ============================================================

    def _analyze(
        self,
        content: WebsiteContent,
    ) -> KnowledgeValidationLLMResult:
        logger.info("Calling LLM for knowledge validation.")

        structured_llm = self.llm.with_structured_output(
            KnowledgeValidationLLMResult
        )

        try:
            result = structured_llm.invoke(
                self._build_prompt(content)
            )
        except Exception:
            logger.exception(
                "Knowledge validation LLM call failed."
            )
            raise

        logger.info("Knowledge validation LLM call successful.")

        return result

    # ============================================================
    # PARALLEL PROPERTY CARD VALIDATION
    # ============================================================

    def _validate_property_cards(
        self,
        content: WebsiteContent,
    ) -> tuple[list[Issue], list[Recommendation]]:
        property_cards = getattr(
            content,
            "property_cards",
            [],
        )

        logger.info(
            "Property card validation started | cards=%d | workers=%d",
            len(property_cards),
            self.max_workers,
        )

        if not property_cards:
            return [], []

        issues: list[Issue] = []
        recommendations: list[Recommendation] = []

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:

            futures = {
                executor.submit(
                    self._validate_single_property_card,
                    content,
                    card,
                ): card
                for card in property_cards
            }

            for future in as_completed(futures):
                card = futures[future]

                try:
                    card_issue, card_recommendation = (
                        future.result()
                    )

                except Exception:
                    logger.exception(
                        "Property card validation failed | "
                        "title=%s",
                        getattr(card, "title", ""),
                    )
                    continue

                if card_issue:
                    issues.append(card_issue)

                if card_recommendation:
                    recommendations.append(
                        card_recommendation
                    )

        logger.info(
            "Property card validation completed | "
            "issues=%d | recommendations=%d",
            len(issues),
            len(recommendations),
        )

        return issues, recommendations

    def _validate_single_property_card(
        self,
        content: WebsiteContent,
        card,
    ) -> tuple[Issue | None, Recommendation | None]:

        title = getattr(
            card,
            "title",
            "Unknown property",
        )

        location = getattr(
            card,
            "location",
            "",
        )

        logger.info(
            "Validating property card | title=%s | location=%s",
            title,
            location,
        )

        result = self._validate_property_card(
            content,
            card,
        )

        if result.status != "context_mismatch":
            return None, None

        reason = result.reason.strip()

        description = (
            f"The property card '{title}'"
        )

        if location:
            description += (
                f" is associated with {location}."
            )

        if reason:
            description += f" {reason}"

        issue = Issue(
            severity="High",
            title="Property Card Context Mismatch",
            description=description,
        )

        recommendation = Recommendation(
            title="Review Property Card",
            description=(
                f"Review the '{title}' property card "
                f"and remove or replace it if it does not "
                f"belong to the webpage's destination. "
                f"The card location is '{location}'."
            ),
        )

        logger.warning(
            "Property card context mismatch | "
            "title=%s | location=%s | reason=%s",
            title,
            location,
            reason,
        )

        return issue, recommendation

    def _validate_property_card(
        self,
        content: WebsiteContent,
        card,
    ) -> PropertyCardValidationLLMResult:

        structured_llm = self.llm.with_structured_output(
            PropertyCardValidationLLMResult
        )

        return structured_llm.invoke(
            self._build_property_card_prompt(
                content,
                card,
            )
        )

    # ============================================================
    # PROPERTY CARD PROMPT
    # ============================================================

    @staticmethod
    def _build_property_card_prompt(
        content: WebsiteContent,
        card,
    ) -> str:

        headings = [
            heading
            for heading_list in (
                content.headings.h1,
                content.headings.h2,
                content.headings.h3,
                content.headings.h4,
            )
            for heading in heading_list
        ]

        return f"""
You are validating ONE PROPERTY CARD on a travel webpage.

Your ONLY task is to determine whether this property card belongs
to the destination/context of the webpage.

PAGE TITLE:
{content.title}

PAGE HEADINGS:
{headings}

PROPERTY TITLE:
{getattr(card, "title", "")}

CITY:
{getattr(card, "city", "")}

COUNTRY:
{getattr(card, "country", "")}

COUNTRY CODE:
{getattr(card, "country_code", "")}

LOCATION:
{getattr(card, "location", "")}

PROPERTY TYPE:
{getattr(card, "property_type", "")}

PAGE CONTEXT:
{content.plain_text[:6000]}

TASK:
Determine whether the property card is contextually appropriate
for this webpage.

VALID:
The property is reasonably relevant to the webpage destination.

CONTEXT_MISMATCH:
The property clearly belongs to a different destination.

Nearby cities, metropolitan areas, suburbs, and directly relevant
travel areas should NOT automatically be considered mismatches.

Examples:

New York City page + New York City hotel = valid.

New York City page + Jersey City hotel = valid.

New York City page + Paris hotel = context_mismatch.

London page + New York hotel = context_mismatch.

Do NOT evaluate:
- HTML
- SEO
- keyword density
- readability
- writing quality
- page design

Do not invent facts.

Return ONLY the structured result.

status:
- valid
- context_mismatch

reason:
Give a short, concrete explanation.
"""

    # ============================================================
    # GENERAL KNOWLEDGE PROMPT
    # ============================================================

    @staticmethod
    def _build_prompt(
        content: WebsiteContent,
    ) -> str:

        headings = [
            heading
            for heading_list in (
                content.headings.h1,
                content.headings.h2,
                content.headings.h3,
                content.headings.h4,
            )
            for heading in heading_list
        ]

        return f"""
You are a factual-content validator for an AI-generated travel webpage.

Your ONLY responsibility is KNOWLEDGE VALIDATION.

Check whether factual claims on the webpage are supported by reliable
external information.

PAGE TITLE:
{content.title}

HEADINGS:
{headings}

WEBPAGE CONTENT:
{content.plain_text[:16000]}

CHECK FOR:

1. Incorrect factual claims.
2. Unsupported factual claims.
3. Contradictory claims.
4. Incorrect destination information.
5. Incorrect attraction/location information.
6. Incorrect travel information.
7. Incorrect hotel/property information.
8. Destination mismatches.

Property cards are validated separately.

Do NOT evaluate:
- SEO
- HTML
- keyword density
- readability
- writing style
- AI-generated writing style

Every issue MUST identify where it appears.

Use:
- section heading
- card title
- paragraph context
- heading
- list item

Do not write vague issues.

SEARCH / VERIFICATION:

Use external search evidence when factual verification is required.

Do not claim something is false merely because evidence is unavailable.

If evidence is insufficient, classify the claim as uncertain.

SCORING:

100:
Claims are well-supported with no meaningful factual problems.

80-99:
Mostly accurate with minor unsupported or uncertain claims.

60-79:
Several claims require verification or contain questionable details.

40-59:
Significant factual problems exist.

0-39:
Major factual inaccuracies or destination mismatches exist.

Return only concrete findings.
Do not generate generic warnings.
Return the required structured output.
"""

    @staticmethod
    def _issue_severity(score: int) -> str:
        if score < 40:
            return "High"
        if score < 70:
            return "Medium"
        return "Low"

#working tooo

# import logging

# from pydantic import BaseModel, Field

# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import (
#     Issue,
#     KnowledgeValidationResult,
#     Recommendation,
# )


# logger = logging.getLogger(__name__)


# class ClaimValidationLLMResult(BaseModel):
#     status: str = Field(
#         description="verified, unsupported, or uncertain"
#     )

#     claim: str = ""

#     evidence: str = ""

#     location: str = ""

#     explanation: str = ""


# class PropertyCardValidationLLMResult(BaseModel):
#     status: str = Field(
#         description="valid or context_mismatch"
#     )

#     reason: str = ""


# class KnowledgeValidationLLMResult(BaseModel):
#     score: int = Field(
#         ge=0,
#         le=100,
#     )

#     verified_claims: list[str] = Field(
#         default_factory=list
#     )

#     unsupported_claims: list[str] = Field(
#         default_factory=list
#     )

#     uncertain_claims: list[str] = Field(
#         default_factory=list
#     )

#     issues: list[str] = Field(
#         default_factory=list
#     )

#     recommendations: list[str] = Field(
#         default_factory=list
#     )


# class KnowledgeValidationEvaluator:

#     def __init__(
#         self,
#         llm,
#         search_client,
#         max_workers: int = 3,
#     ):
#         self.llm = llm
#         self.search_client = search_client
#         self.max_workers = max_workers

#         logger.info(
#             "KnowledgeValidationEvaluator initialized | llm=%s | search_client=%s | max_workers=%d",
#             type(llm).__name__,
#             type(search_client).__name__,
#             max_workers,
#         )

#     def evaluate(
#         self,
#         content: WebsiteContent,
#     ) -> KnowledgeValidationResult:

#         logger.info(
#             "Knowledge validation evaluation started."
#         )

#         # ---------------------------------------------------------
#         # 1. GENERAL KNOWLEDGE / CLAIM VALIDATION
#         # ---------------------------------------------------------

#         result = self._analyze(content)

#         issues = [
#             Issue(
#                 severity=self._issue_severity(result.score),
#                 title="Knowledge Validation",
#                 description=issue,
#             )
#             for issue in result.issues
#         ]

#         recommendations = [
#             Recommendation(
#                 title="Fix Knowledge Issue",
#                 description=recommendation,
#             )
#             for recommendation in result.recommendations
#         ]

#         # ---------------------------------------------------------
#         # 2. PROPERTY CARD VALIDATION
#         # ---------------------------------------------------------

#         card_issues, card_recommendations = (
#             self._validate_property_cards(content)
#         )

#         issues.extend(card_issues)
#         recommendations.extend(card_recommendations)

#         # ---------------------------------------------------------
#         # 3. FINAL SCORE
#         # ---------------------------------------------------------

#         score = result.score

#         # Every context-mismatched property card has a significant
#         # effect on knowledge/content correctness.
#         if card_issues:
#             card_penalty = len(card_issues) * 15

#             score = max(
#                 0,
#                 score - card_penalty,
#             )

#         logger.info(
#             "Knowledge validation completed | "
#             "base_score=%d | card_issues=%d | final_score=%d",
#             result.score,
#             len(card_issues),
#             score,
#         )

#         return KnowledgeValidationResult(
#             score=score,
#             issues=issues,
#             recommendations=recommendations,
#             verified_claims=result.verified_claims,
#             unsupported_claims=result.unsupported_claims,
#             uncertain_claims=result.uncertain_claims,
#         )

#     # =============================================================
#     # GENERAL CLAIM VALIDATION
#     # =============================================================

#     def _analyze(
#         self,
#         content: WebsiteContent,
#     ) -> KnowledgeValidationLLMResult:

#         logger.info(
#             "Calling LLM for knowledge validation."
#         )

#         structured_llm = self.llm.with_structured_output(
#             KnowledgeValidationLLMResult
#         )

#         prompt = self._build_prompt(content)

#         try:
#             result = structured_llm.invoke(prompt)

#         except Exception:

#             logger.exception(
#                 "Knowledge validation LLM call failed."
#             )

#             raise

#         logger.info(
#             "Knowledge validation LLM call successful."
#         )

#         return result

#     # =============================================================
#     # PROPERTY CARD VALIDATION
#     # =============================================================

#     def _validate_property_cards(
#         self,
#         content: WebsiteContent,
#     ) -> tuple[list[Issue], list[Recommendation]]:

#         issues: list[Issue] = []
#         recommendations: list[Recommendation] = []

#         property_cards = getattr(
#             content,
#             "property_cards",
#             [],
#         )

#         logger.info(
#             "Property card validation started | cards=%d",
#             len(property_cards),
#         )

#         if not property_cards:

#             logger.info(
#                 "No property cards found."
#             )

#             return issues, recommendations

#         for card in property_cards:

#             logger.info(
#                 "Validating property card | title=%s | location=%s",
#                 getattr(card, "title", ""),
#                 getattr(card, "location", ""),
#             )

#             try:

#                 result = self._validate_property_card(
#                     content,
#                     card,
#                 )

#             except Exception:

#                 logger.exception(
#                     "Property card validation failed | title=%s",
#                     getattr(card, "title", ""),
#                 )

#                 continue

#             if result.status == "context_mismatch":

#                 title = getattr(
#                     card,
#                     "title",
#                     "Unknown property",
#                 )

#                 location = getattr(
#                     card,
#                     "location",
#                     "",
#                 )

#                 reason = result.reason.strip()

#                 description = (
#                     f"The property card '{title}'"
#                 )

#                 if location:
#                     description += (
#                         f" is associated with {location}."
#                     )

#                 if reason:
#                     description += (
#                         f" {reason}"
#                     )

#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Property Card Context Mismatch",
#                         description=description,
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Review Property Card",
#                         description=(
#                             f"Review the '{title}' property card "
#                             f"and remove or replace it if it does not "
#                             f"belong to the webpage's destination. "
#                             f"The card location is '{location}'."
#                         ),
#                     )
#                 )

#                 logger.warning(
#                     "Property card context mismatch | "
#                     "title=%s | location=%s | reason=%s",
#                     title,
#                     location,
#                     reason,
#                 )

#         logger.info(
#             "Property card validation completed | issues=%d",
#             len(issues),
#         )

#         return issues, recommendations

#     def _validate_property_card(
#         self,
#         content: WebsiteContent,
#         card,
#     ) -> PropertyCardValidationLLMResult:

#         structured_llm = self.llm.with_structured_output(
#             PropertyCardValidationLLMResult
#         )

#         prompt = self._build_property_card_prompt(
#             content,
#             card,
#         )

#         return structured_llm.invoke(prompt)

#     # =============================================================
#     # PROPERTY CARD PROMPT
#     # =============================================================

#     @staticmethod
#     def _build_property_card_prompt(
#         content: WebsiteContent,
#         card,
#     ) -> str:

#         headings: list[str] = []

#         for heading_list in (
#             content.headings.h1,
#             content.headings.h2,
#             content.headings.h3,
#             content.headings.h4,
#         ):
#             headings.extend(
#                 heading_list
#             )

#         return f"""
# You are validating ONE PROPERTY CARD on a travel webpage.

# Your ONLY task is to determine whether this property card belongs
# to the destination/context of the webpage.

# ================ PAGE =================

# PAGE TITLE:
# {content.title}

# PAGE HEADINGS:
# {headings}

# ================ PROPERTY CARD =================

# PROPERTY TITLE:
# {getattr(card, "title", "")}

# CITY:
# {getattr(card, "city", "")}

# COUNTRY:
# {getattr(card, "country", "")}

# COUNTRY CODE:
# {getattr(card, "country_code", "")}

# LOCATION:
# {getattr(card, "location", "")}

# PROPERTY TYPE:
# {getattr(card, "property_type", "")}

# ================ PAGE CONTEXT =================

# {content.plain_text[:6000]}

# ================ TASK =================

# Determine whether the property card is contextually appropriate
# for this webpage.

# Examples:

# Example 1:

# Page:
# New York City Travel Guide

# Property:
# Hotel in New York City, USA

# Result:
# valid

# Example 2:

# Page:
# New York City Travel Guide

# Property:
# Hotel in Jersey City, USA

# Result:
# valid

# Reason:
# Jersey City is part of the New York metropolitan/travel area
# and may reasonably be relevant to a New York City travel page.

# Example 3:

# Page:
# New York City Travel Guide

# Property:
# Hotel in Paris, France

# Result:
# context_mismatch

# Example 4:

# Page:
# London Travel Guide

# Property:
# Hotel in New York, USA

# Result:
# context_mismatch

# ================ IMPORTANT RULES =================

# Return "valid" when the property is reasonably relevant to the
# webpage destination.

# Return "context_mismatch" only when the property clearly belongs
# to a different destination.

# Nearby cities, metropolitan areas, suburbs, and directly relevant
# travel areas should NOT automatically be considered mismatches.

# Do not evaluate:

# - HTML
# - SEO
# - keyword density
# - writing quality
# - readability
# - page design

# Do not invent facts.

# Return ONLY the required structured result.

# status:
# - valid
# - context_mismatch

# reason:
# Give a short, concrete explanation.
# """

#     # =============================================================
#     # GENERAL KNOWLEDGE PROMPT
#     # =============================================================

#     @staticmethod
#     def _build_prompt(
#         content: WebsiteContent,
#     ) -> str:

#         headings = []

#         for heading_list in (
#             content.headings.h1,
#             content.headings.h2,
#             content.headings.h3,
#             content.headings.h4,
#         ):
#             headings.extend(
#                 heading_list
#             )

#         return f"""
# You are a factual-content validator for an AI-generated travel webpage.

# Your ONLY responsibility is KNOWLEDGE VALIDATION.

# Check whether factual claims on the webpage are supported by reliable
# external information.

# ================ PAGE TITLE ================

# {content.title}

# ================ HEADINGS ================

# {headings}

# ================ WEBPAGE CONTENT ================

# {content.plain_text[:16000]}

# ================ CHECK THESE ================

# Look for:

# 1. Incorrect factual claims.
# 2. Unsupported factual claims.
# 3. Claims that appear contradictory.
# 4. Incorrect destination information.
# 5. Incorrect attraction/location information.
# 6. Incorrect travel-related information.
# 7. Incorrect hotel/property information.
# 8. Destination mismatch inside cards or structured content.

# IMPORTANT:

# Property cards are validated separately.

# Do NOT assume that a property card is valid merely because it appears
# on the page.

# Do NOT evaluate:

# - SEO
# - HTML
# - keyword density
# - readability
# - writing style
# - AI-generated writing style

# ================ LOCATION OF ISSUE ================

# Every issue MUST identify where it appears.

# Use:

# - section heading
# - card title
# - paragraph context
# - heading
# - list item

# Do NOT write vague issues.

# ================ SEARCH / VERIFICATION ================

# Use external search evidence when factual verification is required.

# Do not claim something is false merely because evidence is not
# immediately available.

# If evidence is insufficient, classify the claim as uncertain.

# ================ SCORING ================

# 100:
# Claims are well-supported and no meaningful factual problems exist.

# 80-99:
# Mostly accurate with minor unsupported or uncertain claims.

# 60-79:
# Several claims require verification or contain questionable details.

# 40-59:
# Significant factual problems exist.

# 0-39:
# Major factual inaccuracies or destination mismatches exist.

# Return only concrete findings.

# Do not generate generic warnings.

# Return the required structured output.
# """

#     @staticmethod
#     def _issue_severity(
#         score: int,
#     ) -> str:

#         if score < 40:
#             return "High"

#         if score < 70:
#             return "Medium"

#         return "Low"

## this workssss!!!!!
# import logging
# from concurrent.futures import ThreadPoolExecutor, as_completed

# from pydantic import BaseModel, Field

# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import (
#     Issue,
#     KnowledgeValidationResult,
#     Recommendation,
# )


# logger = logging.getLogger(__name__)


# class ClaimValidationLLMResult(BaseModel):
#     status: str = Field(
#         description="verified, unsupported, or uncertain"
#     )

#     claim: str = ""

#     evidence: str = ""

#     location: str = ""

#     explanation: str = ""


# class KnowledgeValidationLLMResult(BaseModel):
#     score: int = Field(
#         ge=0,
#         le=100,
#     )

#     verified_claims: list[str] = Field(
#         default_factory=list
#     )

#     unsupported_claims: list[str] = Field(
#         default_factory=list
#     )

#     uncertain_claims: list[str] = Field(
#         default_factory=list
#     )

#     issues: list[str] = Field(
#         default_factory=list
#     )

#     recommendations: list[str] = Field(
#         default_factory=list
#     )


# class KnowledgeValidationEvaluator:

#     def __init__(
#         self,
#         llm,
#         search_client,
#         max_workers: int = 3,
#     ):
#         self.llm = llm
#         self.search_client = search_client
#         self.max_workers = max_workers

#         logger.info(
#             "KnowledgeValidationEvaluator initialized | llm=%s | search_client=%s | max_workers=%d",
#             type(llm).__name__,
#             type(search_client).__name__,
#             max_workers,
#         )

#     def evaluate(
#         self,
#         content: WebsiteContent,
#     ) -> KnowledgeValidationResult:

#         logger.info(
#             "Knowledge validation evaluation started."
#         )

#         result = self._analyze(content)

#         issues = [
#             Issue(
#                 severity=self._issue_severity(result.score),
#                 title="Knowledge Validation",
#                 description=issue,
#             )
#             for issue in result.issues
#         ]

#         recommendations = [
#             Recommendation(
#                 title="Fix Knowledge Issue",
#                 description=recommendation,
#             )
#             for recommendation in result.recommendations
#         ]

#         logger.info(
#             "Knowledge validation completed | score=%d | issues=%d",
#             result.score,
#             len(issues),
#         )

#         return KnowledgeValidationResult(
#             score=result.score,
#             issues=issues,
#             recommendations=recommendations,
#             verified_claims=result.verified_claims,
#             unsupported_claims=result.unsupported_claims,
#             uncertain_claims=result.uncertain_claims,
#         )

#     def _analyze(
#         self,
#         content: WebsiteContent,
#     ) -> KnowledgeValidationLLMResult:

#         logger.info(
#             "Calling LLM for knowledge validation."
#         )

#         structured_llm = self.llm.with_structured_output(
#             KnowledgeValidationLLMResult
#         )

#         prompt = self._build_prompt(content)

#         result = structured_llm.invoke(prompt)

#         logger.info(
#             "Knowledge validation LLM call successful."
#         )

#         return result

#     @staticmethod
#     def _build_prompt(
#         content: WebsiteContent,
#     ) -> str:

#         headings = []

#         for heading_list in (
#             content.headings.h1,
#             content.headings.h2,
#             content.headings.h3,
#             content.headings.h4,
#         ):
#             headings.extend(heading_list)

#         return f"""
# You are a factual-content validator for an AI-generated travel webpage.

# Your ONLY responsibility is KNOWLEDGE VALIDATION.

# Check whether factual claims on the webpage are supported by reliable
# external information.

# ================ PAGE TITLE ================
# {content.title}

# ================ HEADINGS ================
# {headings}

# ================ WEBPAGE CONTENT ================
# {content.plain_text[:16000]}

# ================ CHECK THESE ================

# Look for:

# 1. Incorrect factual claims.
# 2. Unsupported factual claims.
# 3. Claims that appear contradictory.
# 4. Incorrect destination information.
# 5. Incorrect attraction/location information.
# 6. Incorrect travel-related information.
# 7. Incorrect hotel/property/card information.
# 8. Destination mismatch inside cards or structured-looking content.

# IMPORTANT:

# If a card says one destination but its content describes another
# destination, treat that as a knowledge/content mismatch.

# Example:

# Card title:
# "London Travel Guide"

# Card description:
# "Explore the best restaurants in New York."

# This is a destination/content mismatch.

# ================ LOCATION OF ISSUE ================

# Every issue MUST identify where it appears.

# Use:

# - section heading
# - card title
# - paragraph context
# - heading
# - list item

# Example:

# "In the 'Top Restaurants' card, the description refers to New York
# restaurants although the page is about London."

# Do NOT write vague issues.

# ================ SEARCH / VERIFICATION ================

# Use external search evidence when factual verification is required.

# Do not claim that something is false merely because you cannot find
# evidence immediately.

# If evidence is insufficient, classify the claim as uncertain rather
# than false.

# Do NOT evaluate:

# - SEO
# - HTML
# - keyword density
# - readability
# - writing style
# - AI-generated writing style

# ================ SCORING ================

# 100:
# Claims are well-supported and no meaningful factual problems exist.

# 80-99:
# Mostly accurate with minor unsupported or uncertain claims.

# 60-79:
# Several claims require verification or contain questionable details.

# 40-59:
# Significant factual problems exist.

# 0-39:
# Major factual inaccuracies or destination mismatches exist.

# Return only concrete findings.

# Do not generate generic warnings.

# Return the required structured output.
# """

#     @staticmethod
#     def _issue_severity(score: int) -> str:

#         if score < 40:
#             return "High"

#         if score < 70:
#             return "Medium"

#         return "Low"

