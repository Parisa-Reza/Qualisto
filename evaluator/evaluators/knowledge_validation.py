import logging
import re
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
    """Represents the validation result of a single factual claim.

    Parameters:
        status: Validation status of the claim.
        claim: The factual claim being evaluated.
        evidence: Evidence supporting the validation.
        location: Location of the claim on the webpage.
        explanation: Explanation of the validation result.

    Returns:
        A structured claim-validation result.
    """

    status: str = Field(
        description="verified, unsupported, or uncertain"
    )
    claim: str = ""
    evidence: str = ""
    location: str = ""
    explanation: str = ""


class PropertyCardBatchItem(BaseModel):
    """Represents validation output for one property card.

    Parameters:
        card_index: Index of the property card in the validation batch.
        status: Whether the card is valid or contextually mismatched.
        reason: Short explanation for the decision.

    Returns:
        A structured property-card validation result.
    """

    card_index: int
    status: str = Field(
        description="valid or context_mismatch"
    )
    reason: str = ""


class PropertyCardBatchValidationLLMResult(BaseModel):
    """Represents validation results for multiple property cards.

    Parameters:
        results: Validation result for every ambiguous property card.

    Returns:
        A structured batch validation result.
    """

    results: list[PropertyCardBatchItem] = Field(
        default_factory=list
    )


class KnowledgeValidationLLMResult(BaseModel):
    """Represents the general knowledge-validation result.

    Parameters:
        score: Knowledge-validation score from 0 to 100.
        verified_claims: Claims supported by evidence.
        unsupported_claims: Claims lacking reliable support.
        uncertain_claims: Claims that cannot be confidently verified.
        issues: Concrete knowledge issues.
        recommendations: Recommended corrections.

    Returns:
        A structured knowledge-validation result.
    """

    score: int = Field(ge=0, le=100)
    verified_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class KnowledgeValidationEvaluator:
    """Validates webpage knowledge using the user prompt and web evidence.

    Parameters:
        llm: Local or remote language model used for structured validation.
        search_client: Tavily-compatible search client.
        max_workers: Number of workers used only for external searches.

    Returns:
        An evaluator capable of validating general knowledge and
        property-card contextual relevance.
    """

    def __init__(
        self,
        llm,
        search_client,
        max_workers: int = 4,
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
        user_prompt: str,
    ) -> KnowledgeValidationResult:
        """Evaluate webpage knowledge against the user's original prompt.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original prompt describing the intended webpage.

        Returns:
            KnowledgeValidationResult containing scores, issues,
            recommendations, and classified claims.
        """

        logger.info(
            "Knowledge validation started | user_prompt=%s",
            user_prompt[:300],
        )

        general_result = self._analyze(
            content=content,
            user_prompt=user_prompt,
        )

        issues = [
            Issue(
                severity=self._issue_severity(
                    general_result.score
                ),
                title="Knowledge Validation",
                description=issue,
            )
            for issue in general_result.issues
        ]

        recommendations = [
            Recommendation(
                title="Fix Knowledge Issue",
                description=recommendation,
            )
            for recommendation in general_result.recommendations
        ]

        card_issues, card_recommendations = (
            self._validate_property_cards(
                content=content,
                user_prompt=user_prompt,
            )
        )

        issues.extend(card_issues)
        recommendations.extend(card_recommendations)

        score = max(
            0,
            general_result.score - len(card_issues) * 15,
        )

        logger.info(
            "Knowledge validation completed | "
            "base_score=%d | card_issues=%d | final_score=%d",
            general_result.score,
            len(card_issues),
            score,
        )

        return KnowledgeValidationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
            verified_claims=general_result.verified_claims,
            unsupported_claims=general_result.unsupported_claims,
            uncertain_claims=general_result.uncertain_claims,
        )


    # GENERAL KNOWLEDGE VALIDATION


    def _analyze(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> KnowledgeValidationLLMResult:
        """Validate general webpage claims against the user intent.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Structured general knowledge-validation result.
        """

        logger.info(
            "General knowledge validation started."
        )

        search_evidence = self._collect_search_evidence(
            content=content,
            user_prompt=user_prompt,
        )

        logger.info(
            "Collected %d characters of search evidence.",
            len(search_evidence),
        )

        structured_llm = self.llm.with_structured_output(
            KnowledgeValidationLLMResult
        )

        try:
            result = structured_llm.invoke(
                self._build_prompt(
                    content=content,
                    user_prompt=user_prompt,
                    search_evidence=search_evidence,
                )
            )
        except Exception:
            logger.exception(
                "General knowledge validation LLM call failed."
            )
            raise

        logger.info(
            "General knowledge validation LLM call successful."
        )

        return result


    # PROPERTY CARD VALIDATION


    def _validate_property_cards(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> tuple[list[Issue], list[Recommendation]]:
        """Validate property-card destination relevance efficiently.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Issues and recommendations generated from invalid cards.
        """

        property_cards = getattr(
            content,
            "property_cards",
            [],
        )

        logger.info(
            "Property card validation started | cards=%d",
            len(property_cards),
        )

        if not property_cards:
            return [], []

        deterministic_valid = []
        deterministic_invalid = []
        ambiguous_cards = []

        for index, card in enumerate(property_cards):
            decision = self._deterministic_card_match(
                card=card,
                user_prompt=user_prompt,
            )

            logger.info(
                "Property card pre-validation | "
                "index=%d | title=%s | decision=%s",
                index,
                getattr(card, "title", ""),
                decision,
            )

            if decision == "valid":
                deterministic_valid.append(
                    (index, card)
                )

            elif decision == "context_mismatch":
                deterministic_invalid.append(
                    (index, card)
                )

            else:
                ambiguous_cards.append(
                    (index, card)
                )

        logger.info(
            "Property card pre-validation completed | "
            "valid=%d | invalid=%d | ambiguous=%d",
            len(deterministic_valid),
            len(deterministic_invalid),
            len(ambiguous_cards),
        )

        issues = []
        recommendations = []

        for _, card in deterministic_invalid:
            issue, recommendation = (
                self._build_property_card_issue(
                    card=card,
                    reason=(
                        "The property card destination does not "
                        "match the destination specified by the "
                        "user's prompt."
                    ),
                )
            )

            issues.append(issue)
            recommendations.append(recommendation)

        if not ambiguous_cards:
            return issues, recommendations

        tavily_evidence = self._collect_card_evidence_parallel(
            content=content,
            ambiguous_cards=ambiguous_cards,
        )

        llm_results = self._validate_ambiguous_cards_batch(
            content=content,
            user_prompt=user_prompt,
            ambiguous_cards=ambiguous_cards,
            tavily_evidence=tavily_evidence,
        )

        for index, card in ambiguous_cards:
            result = llm_results.get(index)

            if not result:
                logger.warning(
                    "No LLM result returned for card index=%d",
                    index,
                )
                continue

            if result.status != "context_mismatch":
                continue

            issue, recommendation = (
                self._build_property_card_issue(
                    card=card,
                    reason=result.reason,
                )
            )

            issues.append(issue)
            recommendations.append(recommendation)

        logger.info(
            "Property card validation completed | "
            "issues=%d | recommendations=%d",
            len(issues),
            len(recommendations),
        )

        return issues, recommendations


    # DETERMINISTIC PROPERTY CARD FILTER


    @staticmethod
    def _deterministic_card_match(
        card,
        user_prompt: str,
    ) -> str:
        """Perform cheap destination matching before using an LLM.

        Parameters:
            card: Property-card object.
            user_prompt: Original webpage-generation prompt.

        Returns:
            'valid', 'context_mismatch', or 'ambiguous'.
        """

        prompt_text = KnowledgeValidationEvaluator._normalize_text(
            user_prompt
        )

        city = KnowledgeValidationEvaluator._normalize_text(
            getattr(card, "city", "")
        )

        country = KnowledgeValidationEvaluator._normalize_text(
            getattr(card, "country", "")
        )

        location = KnowledgeValidationEvaluator._normalize_text(
            getattr(card, "location", "")
        )

        if not city and not country:
            return "ambiguous"

        city_aliases = (
            KnowledgeValidationEvaluator._destination_aliases(
                city
            )
        )

        country_aliases = (
            KnowledgeValidationEvaluator._destination_aliases(
                country
            )
        )

        city_match = any(
            alias in prompt_text
            for alias in city_aliases
            if alias
        )

        country_match = any(
            alias in prompt_text
            for alias in country_aliases
            if alias
        )

        location_match = bool(
            location
            and location in prompt_text
        )

        if city_match:
            return "valid"

        if location_match:
            return "valid"

        if country_match and not city:
            return "valid"

        if city and not city_match:
            return "ambiguous"

        if country and not country_match:
            return "ambiguous"

        return "ambiguous"

    @staticmethod
    def _destination_aliases(
        destination: str,
    ) -> set[str]:
        """Generate simple aliases for a destination.

        Parameters:
            destination: Destination name.

        Returns:
            Normalized destination aliases.
        """

        destination = destination.strip()

        if not destination:
            return set()

        aliases = {destination}

        compact = destination.replace(" ", "")

        if compact:
            aliases.add(compact)

        known_aliases = {
            "new york city": {
                "new york",
                "nyc",
                "new york city",
            },
            "bali": {
                "bali",
            },
            "london": {
                "london",
            },
            "paris": {
                "paris",
            },
            "tokyo": {
                "tokyo",
            },
        }

        aliases.update(
            known_aliases.get(
                destination,
                set(),
            )
        )

        return {
            alias
            for alias in aliases
            if alias
        }

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """Normalize text for deterministic destination matching.

        Parameters:
            value: Input text.

        Returns:
            Lowercase normalized text.
        """

        value = value.lower()
        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )
        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()


    # TAVILY CARD SEARCH


    def _collect_card_evidence_parallel(
        self,
        content: WebsiteContent,
        ambiguous_cards,
    ) -> dict[int, str]:
        """Collect Tavily evidence for ambiguous cards.

        Parameters:
            content: Extracted webpage content.
            ambiguous_cards: Cards requiring external verification.

        Returns:
            Mapping from card index to Tavily evidence.
        """

        if not self.search_client:
            return {}

        evidence = {}

        with ThreadPoolExecutor(
            max_workers=min(
                self.max_workers,
                max(1, len(ambiguous_cards)),
            )
        ) as executor:

            futures = {
                executor.submit(
                    self._collect_single_card_evidence,
                    content,
                    index,
                    card,
                ): index
                for index, card in ambiguous_cards
            }

            for future in as_completed(futures):
                index = futures[future]

                try:
                    evidence[index] = future.result()

                except Exception:
                    logger.exception(
                        "Tavily card search failed | index=%d",
                        index,
                    )
                    evidence[index] = ""

        return evidence

    def _collect_single_card_evidence(
        self,
        content: WebsiteContent,
        index: int,
        card,
    ) -> str:
        """Search external sources for one ambiguous property card.

        Parameters:
            content: Extracted webpage content.
            index: Property-card index.
            card: Property-card object.

        Returns:
            Formatted Tavily evidence.
        """

        query = self._build_card_search_query(
            card=card,
        )

        if not query:
            return ""

        logger.info(
            "Tavily property-card search | index=%d | query=%s",
            index,
            query,
        )

        results = self.search_client.search(
            query=query,
            max_results=3,
        )

        return self._format_search_results(
            results
        )

    @staticmethod
    def _build_card_search_query(
        card,
    ) -> str:
        """Build a concise Tavily query for a property card.

        Parameters:
            card: Property-card object.

        Returns:
            Search query string.
        """

        return " ".join(
            filter(
                None,
                [
                    getattr(card, "title", ""),
                    getattr(card, "city", ""),
                    getattr(card, "country", ""),
                    getattr(card, "location", ""),
                    getattr(card, "property_type", ""),
                ],
            )
        ).split()
    


    # SINGLE BATCH QWEN CALL


    def _validate_ambiguous_cards_batch(
        self,
        content: WebsiteContent,
        user_prompt: str,
        ambiguous_cards,
        tavily_evidence: dict[int, str],
    ) -> dict[int, PropertyCardBatchItem]:
        """Validate all ambiguous cards using ONE LLM invocation.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.
            ambiguous_cards: Cards requiring LLM judgment.
            tavily_evidence: Tavily evidence keyed by card index.

        Returns:
            Mapping from card index to structured validation result.
        """

        if not ambiguous_cards:
            return {}

        logger.info(
            "Starting ONE batched property-card LLM call | cards=%d",
            len(ambiguous_cards),
        )

        structured_llm = self.llm.with_structured_output(
            PropertyCardBatchValidationLLMResult
        )

        cards_text = []

        for index, card in ambiguous_cards:
            cards_text.append(
                f"""
CARD INDEX: {index}

TITLE:
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

TAVILY EVIDENCE:
{tavily_evidence.get(index) or "No external evidence available."}
"""
            )

        prompt = f"""
You are validating property cards on an AI-generated travel webpage.

Your ONLY responsibility is determining whether each property card
belongs to the destination intended by the USER PROMPT.

USER PROMPT:
{user_prompt}

IMPORTANT:
The USER PROMPT is the PRIMARY SOURCE for determining the intended
destination.

Do NOT determine the destination from H1, H2, H3, webpage title,
or webpage content.

Those may be wrong because the webpage itself may have been generated
incorrectly.

The webpage content is provided only as secondary context.

WEBPAGE TITLE:
{content.title}

WEBPAGE HEADINGS:
{content.headings.h1}
{content.headings.h2}
{content.headings.h3}

PROPERTY CARDS TO VALIDATE:
{"".join(cards_text)}

RULES:

1. A property is VALID only when it belongs to the destination
   intended by the user prompt.

2. Nearby cities are NOT automatically valid.

3. Different cities must be treated as different destinations.

Examples:

User prompt: New York City travel guide
New York City hotel -> valid
Manhattan hotel -> valid
Brooklyn hotel -> valid
Jersey City hotel -> context_mismatch
Newark hotel -> context_mismatch
Paris hotel -> context_mismatch

User prompt: London travel guide
London hotel -> valid
Oxford hotel -> context_mismatch
Paris hotel -> context_mismatch

User prompt: Bali travel guide
Bali hotel -> valid
Cox's Bazar hotel -> context_mismatch
Tokyo hotel -> context_mismatch

4. Use Tavily evidence to determine the ACTUAL location of the
   property when necessary.

5. Do not assume a property belongs to a destination merely because
   its name contains the destination name.

6. If the evidence is insufficient to confidently determine whether
   the property belongs to the intended destination, return:
   status=valid

Do not create a false mismatch when evidence is insufficient.

7. Do not evaluate:
   - property images
   - SEO
   - HTML
   - readability
   - writing quality
   - keyword density
   - page design

Return exactly one result for every CARD INDEX.

Use:
status=valid
or
status=context_mismatch

For context_mismatch, provide a short concrete reason.

Return ONLY the structured result.
"""

        try:
            result = structured_llm.invoke(prompt)

        except Exception:
            logger.exception(
                "Batched property-card LLM validation failed."
            )
            return {}

        validated = {
            item.card_index: item
            for item in result.results
        }

        logger.info(
            "Batched property-card LLM validation completed | "
            "results=%d",
            len(validated),
        )

        return validated


    # ISSUE CREATION


    @staticmethod
    def _build_property_card_issue(
        card,
        reason: str,
    ) -> tuple[Issue, Recommendation]:
        """Build issue and recommendation for a mismatched card.

        Parameters:
            card: Invalid property-card object.
            reason: Reason for the mismatch.

        Returns:
            Tuple containing an Issue and Recommendation.
        """

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
                f"Review the '{title}' property card and "
                f"remove or replace it if it does not belong "
                f"to the destination specified by the user. "
                f"The detected card location is "
                f"'{location}'."
            ),
        )

        return issue, recommendation


    # GENERAL SEARCH


    def _collect_search_evidence(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> str:
        """Collect Tavily evidence for general knowledge validation.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Formatted external search evidence.
        """

        if not self.search_client:
            return ""

        query = self._build_search_query(
            content=content,
            user_prompt=user_prompt,
        )

        if not query:
            return ""

        logger.info(
            "Searching Tavily for general knowledge | query=%s",
            query,
        )

        try:
            results = self.search_client.search(
                query=query,
                max_results=5,
            )

        except Exception:
            logger.exception(
                "General Tavily search failed."
            )
            return ""

        return self._format_search_results(
            results
        )

    @staticmethod
    def _build_search_query(
        content: WebsiteContent,
        user_prompt: str,
    ) -> str:
        """Build the general knowledge search query.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Search query string.
        """

        parts = [
            user_prompt,
        ]

        if content.title:
            parts.append(
                content.title
            )

        return " ".join(
            parts
        )[:500]

    @staticmethod
    def _format_search_results(
        results,
    ) -> str:
        """Format Tavily search results for an LLM prompt.

        Parameters:
            results: Tavily search results.

        Returns:
            Human-readable evidence string.
        """

        if not results:
            return ""

        evidence = []

        for index, result in enumerate(
            results,
            start=1,
        ):
            title = result.get(
                "title",
                "",
            )
            url = result.get(
                "url",
                "",
            )
            snippet = result.get(
                "content",
                "",
            )

            evidence.append(
                f"""
Result {index}

Title:
{title}

URL:
{url}

Snippet:
{snippet}
"""
            )

        return "\n".join(
            evidence
        )


    # GENERAL KNOWLEDGE PROMPT


    @staticmethod
    def _build_prompt(
        content: WebsiteContent,
        user_prompt: str,
        search_evidence: str = "",
    ) -> str:
        """Build the general knowledge-validation prompt.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.
            search_evidence: External evidence from Tavily.

        Returns:
            Knowledge-validation prompt.
        """

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

The USER PROMPT is the PRIMARY SOURCE for determining what the webpage
was supposed to be about.

Do NOT assume that the webpage's H1, H2, H3, title, or body content
correctly identifies the intended destination.

The webpage itself may be wrong.

USER PROMPT:
{user_prompt}

PAGE TITLE:
{content.title}

HEADINGS:
{headings}

WEBPAGE CONTENT:
{content.plain_text[:16000]}

SEARCH EVIDENCE:
EXTERNAL SEARCH RESULTS (Tavily):

{search_evidence or "No external evidence was found."}

CHECK FOR:

1. Whether the content matches the destination and subject specified
   by the USER PROMPT.

2. Incorrect factual claims.

3. Unsupported factual claims.

4. Contradictory claims.

5. Incorrect destination information.

6. Incorrect attraction/location information.

7. Incorrect travel information.

8. Incorrect hotel/property information.

9. Content belonging to a different destination than the user requested.

IMPORTANT:

If the USER PROMPT says:

"Create a travel guide for New York City"

but the webpage has:

H1: Best Places to Visit in Japan

H2: Tokyo Attractions

H3: Kyoto Travel Guide

then the webpage is contextually incorrect even if every statement
about Japan is factually correct.

The USER PROMPT determines the intended destination.

Do NOT treat H1/H2/H3 as the authoritative source for destination
identity.

Property cards are validated separately.

Do NOT evaluate:
- SEO
- HTML
- keyword density
- readability
- writing style
- AI-generated writing style
- property-card images

Every issue MUST identify where it appears.

Use:
- section heading
- paragraph context
- heading
- list item
- card title

Do not write vague issues.

SEARCH / VERIFICATION:

Use external search evidence when factual verification is required.

Do not claim something is false merely because evidence is unavailable.

If evidence is insufficient, classify the claim as uncertain.

SCORING:

100:
Claims are well-supported and content strongly matches the user prompt.

80-99:
Mostly accurate with minor unsupported, uncertain, or contextual issues.

60-79:
Several claims require verification or content has noticeable
context problems.

40-59:
Significant factual or destination-context problems exist.

0-39:
Major factual inaccuracies or the webpage is substantially about
the wrong destination.

Return only concrete findings.

Do not generate generic warnings.

Return the required structured output.
"""


    # SEVERITY

    @staticmethod
    def _issue_severity(
        score: int,
    ) -> str:
        """Convert a numerical score into issue severity.

        Parameters:
            score: Knowledge-validation score.

        Returns:
            High, Medium, or Low severity.
        """

        if score < 40:
            return "High"

        if score < 70:
            return "Medium"

        return "Low"