import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel, Field

from evaluator.claim_extractor.claim_extractor import ClaimExtractor
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
    reason: str


class PropertyCardValidationLLMResult(BaseModel):
    status: str = Field(
        description="valid or context_mismatch"
    )
    reason: str


class KnowledgeValidationEvaluator:

    # Keep this small because your local Ollama model is only qwen3:1.7b.
    # 3 workers is a good starting point.
    MAX_WORKERS = 3

    def __init__(
        self,
        llm,
        search_client,
    ):
        self.llm = llm
        self.search_client = search_client

        logger.info(
            "KnowledgeValidationEvaluator initialized | "
            "llm=%s | search_client=%s | max_workers=%d",
            type(llm).__name__,
            type(search_client).__name__,
            self.MAX_WORKERS,
        )

    def evaluate(
        self,
        content: WebsiteContent,
    ) -> KnowledgeValidationResult:

        logger.info("Knowledge validation started.")

        claims = ClaimExtractor.extract(
            content.plain_text
        )

        logger.info(
            "Claims extracted | count=%d",
            len(claims),
        )

        verified_claims = []
        unsupported_claims = []
        uncertain_claims = []
        issues = []
        recommendations = []

        if claims:

            logger.info(
                "Starting parallel claim validation | "
                "claims=%d | workers=%d",
                len(claims),
                min(self.MAX_WORKERS, len(claims)),
            )

            results = self._validate_claims_parallel(
                claims
            )

            logger.info(
                "Parallel claim validation completed."
            )

            # Process results in original claim order.
            for claim, result in results:

                logger.info(
                    "Processing claim result | "
                    "status=%s | claim=%s",
                    result.status,
                    claim,
                )

                if result.status == "verified":

                    verified_claims.append(
                        claim
                    )

                elif result.status == "unsupported":

                    unsupported_claims.append(
                        claim
                    )

                    issues.append(
                        Issue(
                            severity="High",
                            title="Unsupported Claim",
                            description=(
                                f"{claim} "
                                f"Reason: {result.reason}"
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Verify Factual Claim",
                            description=(
                                "Review and verify this claim: "
                                f"{claim}"
                            ),
                        )
                    )

                else:

                    uncertain_claims.append(
                        claim
                    )

                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Uncertain Claim",
                            description=(
                                f"{claim} "
                                f"Reason: {result.reason}"
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Review Uncertain Claim",
                            description=(
                                "Check reliable sources for: "
                                f"{claim}"
                            ),
                        )
                    )

        logger.info(
            "Claim validation completed | "
            "verified=%d | unsupported=%d | uncertain=%d",
            len(verified_claims),
            len(unsupported_claims),
            len(uncertain_claims),
        )

        # ---------------------------------------------------------
        # PROPERTY CARD VALIDATION
        # ---------------------------------------------------------

        logger.info(
            "Starting property-card validation | cards=%d",
            len(content.property_cards),
        )

        card_issues, card_recommendations = (
            self._validate_property_cards(
                content
            )
        )

        issues.extend(card_issues)
        recommendations.extend(
            card_recommendations
        )

        logger.info(
            "Property-card validation completed | issues=%d",
            len(card_issues),
        )

        # ---------------------------------------------------------
        # SCORE
        # ---------------------------------------------------------

        score = self._calculate_score(
            len(claims),
            len(unsupported_claims),
            len(uncertain_claims),
        )

        score = max(
            0,
            score - (len(card_issues) * 15),
        )

        logger.info(
            "Knowledge validation completed | score=%d",
            score,
        )

        return KnowledgeValidationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
            verified_claims=verified_claims,
            unsupported_claims=unsupported_claims,
            uncertain_claims=uncertain_claims,
        )

    # ============================================================
    # PARALLEL CLAIM VALIDATION
    # ============================================================

    def _validate_claims_parallel(
        self,
        claims: list[str],
    ) -> list[
        tuple[str, ClaimValidationLLMResult]
    ]:

        results = []

        worker_count = min(
            self.MAX_WORKERS,
            len(claims),
        )

        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:

            futures = {
                executor.submit(
                    self._validate_single_claim,
                    index,
                    claim,
                ): (index, claim)
                for index, claim in enumerate(
                    claims,
                    start=1,
                )
            }

            for future in as_completed(futures):

                index, claim = futures[future]

                try:

                    result = future.result()

                    results.append(
                        (index, claim, result)
                    )

                    logger.info(
                        "Claim %d/%d completed | status=%s",
                        index,
                        len(claims),
                        result.status,
                    )

                except Exception:

                    logger.exception(
                        "Claim %d/%d failed | claim=%s",
                        index,
                        len(claims),
                        claim,
                    )

                    raise

        # Restore original claim order.
        results.sort(
            key=lambda item: item[0]
        )

        return [
            (claim, result)
            for _, claim, result in results
        ]

    def _validate_single_claim(
        self,
        index: int,
        claim: str,
    ) -> ClaimValidationLLMResult:

        logger.info(
            "Claim %d started | claim=%s",
            index,
            claim,
        )

        # ---------------------------------------------------------
        # TAVILY
        # ---------------------------------------------------------

        logger.info(
            "Claim %d | starting Tavily search",
            index,
        )

        try:

            evidence = self.search_client.search(
                claim,
                max_results=5,
            )

        except Exception:

            logger.exception(
                "Claim %d | Tavily search failed",
                index,
            )

            raise

        logger.info(
            "Claim %d | Tavily search completed | evidence=%d",
            index,
            len(evidence),
        )

        # ---------------------------------------------------------
        # LLM
        # ---------------------------------------------------------

        logger.info(
            "Claim %d | starting LLM validation",
            index,
        )

        result = self._validate_claim(
            claim,
            evidence,
        )

        logger.info(
            "Claim %d | LLM validation completed | status=%s",
            index,
            result.status,
        )

        return result

    # ============================================================
    # SINGLE CLAIM LLM VALIDATION
    # ============================================================

    def _validate_claim(
        self,
        claim: str,
        evidence: list[dict],
    ) -> ClaimValidationLLMResult:

        structured_llm = (
            self.llm.with_structured_output(
                ClaimValidationLLMResult
            )
        )

        try:

            result = structured_llm.invoke(
                self._build_prompt(
                    claim,
                    evidence,
                )
            )

        except Exception:

            logger.exception(
                "Claim validation LLM call failed | claim=%s",
                claim,
            )

            raise

        return result

    # ============================================================
    # PROPERTY CARDS
    # ============================================================

    def _validate_property_cards(
        self,
        content: WebsiteContent,
    ):

        issues = []
        recommendations = []

        cards = content.property_cards

        if not cards:
            logger.info(
                "No property cards found."
            )
            return issues, recommendations

        # Property cards can also be evaluated concurrently.
        worker_count = min(
            self.MAX_WORKERS,
            len(cards),
        )

        logger.info(
            "Starting parallel property-card validation | "
            "cards=%d | workers=%d",
            len(cards),
            worker_count,
        )

        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:

            futures = {
                executor.submit(
                    self._validate_property_card,
                    content,
                    card,
                ): card
                for card in cards
            }

            for future in as_completed(futures):

                card = futures[future]

                try:

                    result = future.result()

                except Exception:

                    logger.exception(
                        "Property-card validation failed | title=%s",
                        card.title,
                    )

                    raise

                logger.info(
                    "Property card validation completed | "
                    "title=%s | status=%s",
                    card.title,
                    result.status,
                )

                if result.status == "context_mismatch":

                    issues.append(
                        Issue(
                            severity="High",
                            title="Property Card Context Mismatch",
                            description=(
                                f"Property '{card.title}' "
                                f"is located in {card.location}. "
                                f"{result.reason}"
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Review Property Card",
                            description=(
                                f"Remove or replace "
                                f"'{card.title}' because its "
                                f"location does not match "
                                f"the webpage destination."
                            ),
                        )
                    )

        return issues, recommendations

    def _validate_property_card(
        self,
        content: WebsiteContent,
        card,
    ) -> PropertyCardValidationLLMResult:

        logger.info(
            "Property-card LLM call started | title=%s",
            card.title,
        )

        structured_llm = (
            self.llm.with_structured_output(
                PropertyCardValidationLLMResult
            )
        )

        try:

            return structured_llm.invoke(
                self._build_property_card_prompt(
                    content,
                    card,
                )
            )

        except Exception:

            logger.exception(
                "Property-card LLM validation failed | title=%s",
                card.title,
            )

            raise

    # ============================================================
    # PROMPTS
    # ============================================================

    @staticmethod
    def _build_property_card_prompt(
        content: WebsiteContent,
        card,
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
Determine whether this property card belongs on this webpage.

PAGE TITLE:
{content.title}

PAGE HEADINGS:
{headings}

PAGE CONTENT CONTEXT:
{content.plain_text[:5000]}

PROPERTY CARD:
Title: {card.title}
City: {card.city}
Country: {card.country}
Country Code: {card.country_code}
Location: {card.location}
Property Type: {card.property_type}

Check whether the property's location is consistent with
the webpage's intended destination.

Examples:

New York City page + Jersey City, USA:
Context mismatch.

New York City page + New York City, USA:
Valid

New York City page + Paris, France:
Context mismatch.

Rules:
- Return "valid" when the property is reasonably relevant
  to the page destination.
- Return "context_mismatch" when it clearly belongs to
  another destination.
- Do not evaluate HTML quality.
- Do not evaluate SEO.
- Do not evaluate keyword density.
- Do not invent facts.

Return the required structured result.
"""

    @staticmethod
    def _build_prompt(
        claim: str,
        evidence: list[dict],
    ) -> str:

        sources = "\n\n".join(
            (
                f"TITLE: {item.get('title', '')}\n"
                f"URL: {item.get('url', '')}\n"
                f"CONTENT: {item.get('content', '')}"
            )
            for item in evidence
        )

        return f"""
Determine whether the following webpage claim is supported
by the provided web evidence.

CLAIM:
{claim}

WEB EVIDENCE:
{sources}

Return:

status:
- verified
- unsupported
- uncertain

Use "verified" only when the evidence clearly supports
the claim.

Use "unsupported" when the evidence contradicts the claim
or provides no credible support.

Use "uncertain" when the evidence is insufficient or
ambiguous.

Do not invent facts.
"""

    @staticmethod
    def _calculate_score(
        total_claims,
        unsupported,
        uncertain,
    ):

        if total_claims == 0:
            return 100

        penalty = (
            unsupported * 20
            + uncertain * 10
        )

        return max(
            0,
            100 - penalty,
        )




# from pydantic import BaseModel, Field
# from evaluator.claim_extractor.claim_extractor import ClaimExtractor
# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import EvaluationResult, Issue, KnowledgeValidationResult, Recommendation


# class ClaimValidationLLMResult(BaseModel):
#     status: str = Field(description="verified, unsupported, or uncertain")
#     reason: str

# class PropertyCardValidationLLMResult(BaseModel):
#     status: str = Field(description="valid or context_mismatch")
#     reason: str


# class KnowledgeValidationEvaluator:
#     def __init__(self, llm, search_client):
#         self.llm = llm
#         self.search_client = search_client

#     def evaluate(self, content: WebsiteContent) -> KnowledgeValidationResult:
#         claims = ClaimExtractor.extract(content.plain_text)
#         verified_claims = []
#         unsupported_claims = []
#         uncertain_claims = []
#         issues = []
#         recommendations = []

   
#         for claim in claims:
#             evidence = self.search_client.search(claim, max_results=5)
#             result = self._validate_claim(claim, evidence)

#             if result.status == "verified":
#                 verified_claims.append(claim)
#             elif result.status == "unsupported":
#                 unsupported_claims.append(claim)
#                 issues.append(Issue(severity="High", title="Unsupported Claim", description=f"{claim} Reason: {result.reason}"))
#                 recommendations.append(Recommendation(title="Verify Factual Claim", description=f"Review and verify this claim: {claim}"))
#             else:
#                 uncertain_claims.append(claim)
#                 issues.append(Issue(severity="Medium", title="Uncertain Claim", description=f"{claim} Reason: {result.reason}"))
#                 recommendations.append(Recommendation(title="Review Uncertain Claim", description=f"Check reliable sources for: {claim}"))

      
#         card_issues, card_recommendations = self._validate_property_cards(content)
#         issues.extend(card_issues)
#         recommendations.extend(card_recommendations)

#         score = self._calculate_score(len(claims), len(unsupported_claims), len(uncertain_claims))

        
#         score = max(0, score - (len(card_issues) * 15))

#         return KnowledgeValidationResult(score=score, issues=issues, recommendations=recommendations, verified_claims=verified_claims, unsupported_claims=unsupported_claims, uncertain_claims=uncertain_claims)

#     def _validate_claim(self, claim: str, evidence: list[dict]) -> ClaimValidationLLMResult:
#         structured_llm = self.llm.with_structured_output(ClaimValidationLLMResult)
#         return structured_llm.invoke(self._build_prompt(claim, evidence))

#     # NEW: validate every extracted property card.
#     def _validate_property_cards(self, content: WebsiteContent):
#         issues = []
#         recommendations = []

#         for card in content.property_cards:
#             result = self._validate_property_card(content, card)

#             if result.status == "context_mismatch":
#                 issues.append(Issue(severity="High", title="Property Card Context Mismatch", description=(f"Property '{card.title}' is located in {card.location}. {result.reason}")))
#                 recommendations.append(Recommendation(title="Review Property Card", description=(f"Remove or replace '{card.title}' because its location does not match the webpage destination.")))

#         return issues, recommendations

   
#     def _validate_property_card(self, content: WebsiteContent, card) -> PropertyCardValidationLLMResult:
#         structured_llm = self.llm.with_structured_output(PropertyCardValidationLLMResult)
#         return structured_llm.invoke(self._build_property_card_prompt(content, card))

  
#     @staticmethod
#     def _build_property_card_prompt(content: WebsiteContent, card) -> str:
#         headings = []
#         for heading_list in (content.headings.h1, content.headings.h2, content.headings.h3):
#             headings.extend(heading_list)

#         return f"""
# Determine whether this property card belongs on this webpage.

# PAGE TITLE:
# {content.title}

# PAGE HEADINGS:
# {headings}

# PAGE CONTENT CONTEXT:
# {content.plain_text[:5000]}

# PROPERTY CARD:
# Title: {card.title}
# City: {card.city}
# Country: {card.country}
# Country Code: {card.country_code}
# Location: {card.location}
# Property Type: {card.property_type}

# Check whether the property's location is consistent with
# the webpage's intended destination.

# Examples:

# New York City page + Jersey City, USA:
# Usually valid because Jersey City is directly relevant
# to the New York City travel area.

# New York City page + Paris, France:
# Context mismatch.

# Rules:
# - Return "valid" when the property is reasonably relevant
#   to the page destination.
# - Return "context_mismatch" when it clearly belongs to
#   another destination.
# - Do not reject a property merely because it is in a
#   nearby city or metropolitan area.
# - Do not evaluate HTML quality.
# - Do not evaluate SEO.
# - Do not evaluate keyword density.
# - Do not invent facts.

# Return the required structured result.
# """

#     @staticmethod
#     def _build_prompt(claim: str, evidence: list[dict]) -> str:
#         sources = "\n\n".join((f"TITLE: {item.get('title', '')}\nURL: {item.get('url', '')}\nCONTENT: {item.get('content', '')}") for item in evidence)

#         return f"""
# Determine whether the following webpage claim is supported
# by the provided web evidence.

# CLAIM:
# {claim}

# WEB EVIDENCE:
# {sources}

# Return:

# status:
# - verified
# - unsupported
# - uncertain

# Use "verified" only when the evidence clearly supports
# the claim.

# Use "unsupported" when the evidence contradicts the claim
# or provides no credible support.

# Use "uncertain" when the evidence is insufficient or
# ambiguous.

# Do not invent facts.
# """

#     @staticmethod
#     def _calculate_score(total_claims, unsupported, uncertain):
#         if total_claims == 0:
#             return 100
#         penalty = unsupported * 20 + uncertain * 10
#         return max(0, 100 - penalty)