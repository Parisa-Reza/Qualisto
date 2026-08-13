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
    """Represents validation output for general webpage knowledge.

    Parameters:
        status: Validation status of the claim.
        claim: Factual claim being evaluated.
        evidence: Supporting evidence.
        location: Claim location on the webpage.
        explanation: Explanation of the validation decision.

    Returns:
        Structured claim-validation information.
    """

    status: str = Field(description="verified, unsupported, or uncertain")
    claim: str = ""
    evidence: str = ""
    location: str = ""
    explanation: str = ""


class DestinationResolutionLLMResult(BaseModel):
    """Represents the resolved destination from the user prompt.

    Parameters:
        destination: Primary destination requested by the user.
        country: Country containing the destination.
        country_code: ISO 3166-1 alpha-2 country code.
        explanation: Explanation of the resolution.

    Returns:
        Structured destination-resolution information.
    """

    destination: str = ""
    country: str = ""
    country_code: str = ""
    explanation: str = ""


class CountryResolutionLLMResult(BaseModel):
    """Represents a dynamically resolved country identity.

    Parameters:
        country: Canonical country name.
        country_code: ISO 3166-1 alpha-2 country code.
        confidence: Confidence in the country resolution.
        explanation: Explanation of the resolution.

    Returns:
        Structured country-resolution information.
    """

    country: str = ""
    country_code: str = ""
    confidence: str = Field(
        default="uncertain",
        description="high, medium, or low",
    )
    explanation: str = ""


class PropertyCardValidationLLMResult(BaseModel):
    """Represents geographic validation of one property card.

    Parameters:
        status: Geographic validation status.
        reason: Explanation for the decision.

    Returns:
        Structured property-card validation result.
    """

    status: str = Field(description="valid or context_mismatch")
    reason: str = ""


class KnowledgeValidationLLMResult(BaseModel):
    """Represents the general knowledge-validation result.

    Parameters:
        score: Knowledge-validation score from 0 to 100.
        verified_claims: Supported factual claims.
        unsupported_claims: Unsupported factual claims.
        uncertain_claims: Claims requiring more evidence.
        issues: Concrete knowledge issues.
        recommendations: Recommended corrections.

    Returns:
        Structured knowledge-validation result.
    """

    score: int = Field(ge=0, le=100)
    verified_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class KnowledgeValidationEvaluator:
    """Validates webpage knowledge and property-card geographic relevance.

    Parameters:
        llm: Language model used for structured validation.
        search_client: Tavily-compatible search client.
        max_workers: Number of workers used for external validation.

    Returns:
        Evaluator capable of validating webpage knowledge and property cards.
    """

    def __init__(self, llm, search_client, max_workers: int = 4):
        self.llm = llm
        self.search_client = search_client
        self.max_workers = max_workers

    def evaluate(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> KnowledgeValidationResult:
        """Evaluate webpage knowledge against the original user prompt.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            KnowledgeValidationResult containing validation findings.
        """
        logger.info(
            "Knowledge validation started | user_prompt=%s",
            user_prompt[:300],
        )

        general_result = self._analyze(content, user_prompt)

        issues = [
            Issue(
                severity=self._issue_severity(general_result.score),
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

        card_issues, card_recommendations, card_score = (
            self._validate_property_cards(
                content,
                user_prompt,
            )
        )

        issues.extend(card_issues)
        recommendations.extend(card_recommendations)

        if getattr(content, "property_cards", []):
            score = min(
                general_result.score,
                card_score,
            )
        else:
            score = general_result.score

        logger.info(
            "Knowledge validation completed | base_score=%d | "
            "card_score=%d | final_score=%d",
            general_result.score,
            card_score,
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

    # ------------------------------------------------------------------
    # GENERAL KNOWLEDGE VALIDATION
    # ------------------------------------------------------------------

    def _analyze(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> KnowledgeValidationLLMResult:
        """Validate general webpage claims against user intent.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Structured general knowledge-validation result.
        """
        search_evidence = self._collect_search_evidence(
            content,
            user_prompt,
        )

        structured_llm = self.llm.with_structured_output(
            KnowledgeValidationLLMResult
        )

        result = structured_llm.invoke(
            self._build_prompt(
                content=content,
                user_prompt=user_prompt,
                search_evidence=search_evidence,
            )
        )

        logger.info(
            "General knowledge validation LLM call successful."
        )

        return result

    # ------------------------------------------------------------------
    # DESTINATION RESOLUTION
    # ------------------------------------------------------------------

    def _resolve_destination(
        self,
        user_prompt: str,
    ) -> dict[str, str]:
        """Resolve destination geography dynamically from the user prompt.

        Parameters:
            user_prompt: Original webpage-generation prompt.

        Returns:
            Dictionary containing destination, country, and country code.
        """
        structured_llm = self.llm.with_structured_output(
            DestinationResolutionLLMResult
        )

        try:
            extracted = structured_llm.invoke(
                self._build_destination_prompt(user_prompt)
            )
        except Exception:
            logger.exception(
                "Destination extraction failed."
            )
            return {}

        destination = self._normalize_text(
            extracted.destination
        )

        country = self._normalize_text(
            extracted.country
        )

        country_code = self._normalize_country_code(
            extracted.country_code
        )

        if not destination:
            return {}

        logger.info(
            "Destination extracted | destination=%s | "
            "country=%s | country_code=%s",
            destination,
            country,
            country_code,
        )

        resolved_country = self._resolve_country_identity(
            country=country,
            country_code=country_code,
            context=extracted.destination,
        )

        if resolved_country:
            country = resolved_country["country"]
            country_code = resolved_country["country_code"]

        if not country or not country_code:
            evidence = self._resolve_destination_with_search(
                extracted.destination
            )

            if evidence:
                try:
                    resolved = structured_llm.invoke(
                        self._build_destination_resolution_prompt(
                            user_prompt=user_prompt,
                            destination=extracted.destination,
                            evidence=evidence,
                        )
                    )

                    resolved_destination = self._normalize_text(
                        resolved.destination
                    )

                    resolved_country = self._normalize_text(
                        resolved.country
                    )

                    resolved_code = self._normalize_country_code(
                        resolved.country_code
                    )

                    if resolved_destination:
                        destination = resolved_destination

                    country_identity = self._resolve_country_identity(
                        country=resolved_country,
                        country_code=resolved_code,
                        context=resolved.destination,
                    )

                    if country_identity:
                        country = country_identity["country"]
                        country_code = country_identity[
                            "country_code"
                        ]

                except Exception:
                    logger.exception(
                        "Destination geographic resolution failed."
                    )

        logger.info(
            "Resolved intended destination | destination=%s | "
            "country=%s | country_code=%s",
            destination,
            country,
            country_code,
        )

        return {
            "destination": destination,
            "country": country,
            "country_code": country_code,
        }

    def _resolve_country_identity(
        self,
        country: str,
        country_code: str,
        context: str = "",
    ) -> dict[str, str]:
        """Resolve a country representation into a canonical country identity.

        Parameters:
            country: Country name or country representation.
            country_code: Candidate ISO country code.
            context: Geographic context used to disambiguate the country.

        Returns:
            Dictionary containing canonical country and ISO country code.
        """
        country = self._normalize_text(country)
        country_code = self._normalize_country_code(
            country_code
        )

        if not country and not country_code:
            return {}

        structured_llm = self.llm.with_structured_output(
            CountryResolutionLLMResult
        )

        evidence = ""

        if self.search_client and (country or country_code):
            query_parts = [
                country,
                country_code,
                context,
                "country ISO 3166 alpha 2",
            ]

            query = " ".join(
                str(value).strip()
                for value in query_parts
                if value
            )

            try:
                results = self.search_client.search(
                    query=query[:400],
                    max_results=5,
                )

                evidence = self._format_search_results(
                    results
                )

            except Exception:
                logger.exception(
                    "Country identity Tavily search failed | "
                    "country=%s | country_code=%s",
                    country,
                    country_code,
                )

        try:
            result = structured_llm.invoke(
                self._build_country_resolution_prompt(
                    country=country,
                    country_code=country_code,
                    context=context,
                    evidence=evidence,
                )
            )
        except Exception:
            logger.exception(
                "Country identity resolution failed | "
                "country=%s | country_code=%s",
                country,
                country_code,
            )
            return {}

        resolved_country = self._normalize_text(
            result.country
        )

        resolved_code = self._normalize_country_code(
            result.country_code
        )

        confidence = (
            str(result.confidence)
            .strip()
            .lower()
        )

        if (
            not resolved_country
            or not resolved_code
            or confidence == "low"
        ):
            logger.warning(
                "Country identity unresolved | input_country=%s | "
                "input_code=%s | resolved_country=%s | "
                "resolved_code=%s | confidence=%s",
                country,
                country_code,
                resolved_country,
                resolved_code,
                confidence,
            )
            return {}

        logger.info(
            "Country identity resolved | input_country=%s | "
            "input_code=%s | canonical_country=%s | "
            "canonical_code=%s",
            country,
            country_code,
            resolved_country,
            resolved_code,
        )

        return {
            "country": resolved_country,
            "country_code": resolved_code,
        }

    @staticmethod
    def _build_country_resolution_prompt(
        country: str,
        country_code: str,
        context: str,
        evidence: str,
    ) -> str:
        """Build the dynamic country identity resolution prompt.

        Parameters:
            country: Country representation to resolve.
            country_code: Candidate ISO country code.
            context: Geographic context.
            evidence: External geographic evidence.

        Returns:
            Country-resolution prompt.
        """
        return f"""
You are a country identity resolution system.

COUNTRY REPRESENTATION:
{country}

CANDIDATE COUNTRY CODE:
{country_code}

GEOGRAPHIC CONTEXT:
{context}

EXTERNAL EVIDENCE:
{evidence or "No external evidence available."}

Resolve the representation into the actual sovereign country.

Rules:

1. Resolve abbreviations, short names, alternative names,
   conventional names, and country representations dynamically.

2. Examples are illustrative only:
   "USA" may refer to "United States".
   "United States of America" may refer to "United States".

3. Do not rely on those examples as a hardcoded mapping.

4. The country_code must be ISO 3166-1 alpha-2.

5. Do not return:
   - state codes
   - province codes
   - city codes
   - airport codes
   - postal codes
   - regional codes
   - marketing abbreviations

6. country and country_code must identify the same sovereign country.

7. Use the external evidence when available.

8. If the representation cannot be resolved confidently,
   return empty country and country_code.

9. Confidence must be:
   high, medium, or low.

Return only structured output.
"""

    def _resolve_destination_with_search(
        self,
        destination: str,
    ) -> str:
        """Search external sources to resolve destination geography.

        Parameters:
            destination: Destination extracted from the user prompt.

        Returns:
            Formatted geographic evidence.
        """
        if not self.search_client or not destination:
            return ""

        query = (
            f"{destination} country official geographic location"
        )

        try:
            results = self.search_client.search(
                query=query,
                max_results=5,
            )
        except Exception:
            logger.exception(
                "Destination Tavily search failed."
            )
            return ""

        return self._format_search_results(results)

    @staticmethod
    def _build_destination_prompt(
        user_prompt: str,
    ) -> str:
        """Build the destination extraction prompt.

        Parameters:
            user_prompt: Original webpage-generation prompt.

        Returns:
            Destination extraction prompt.
        """
        return f"""
You are a geographic destination extraction system.

USER PROMPT:
{user_prompt}

Extract the PRIMARY geographic destination that the requested webpage
is supposed to be about.

Return:
- destination
- country
- country_code
- explanation

Rules:

1. The USER PROMPT is the only authority for destination intent.

2. Ignore webpage titles, headings, property cards, hotel names,
   property locations, and webpage content.

3. Extract the destination the user actually requested.

4. The destination may be a city, municipality, country, state,
   region, island, or other geographic area.

5. Determine the sovereign country containing the destination.

6. country_code must be the ISO 3166-1 alpha-2 code of that country.

7. Do not return state, province, city, airport, postal,
   regional, or marketing codes.

8. If the country is not explicitly stated but the destination
   is geographically unambiguous, the country may be resolved.

9. If the country cannot be resolved confidently, return empty
   country and country_code.

10. Do not derive a country code from letters contained in the
    destination name.

11. Return only structured output.
"""

    @staticmethod
    def _build_destination_resolution_prompt(
        user_prompt: str,
        destination: str,
        evidence: str,
    ) -> str:
        """Build the geographic destination resolution prompt.

        Parameters:
            user_prompt: Original webpage-generation prompt.
            destination: Extracted destination.
            evidence: External geographic evidence.

        Returns:
            Geographic resolution prompt.
        """
        return f"""
You are resolving the geographic identity of a destination.

USER PROMPT:
{user_prompt}

DESTINATION:
{destination}

EXTERNAL GEOGRAPHIC EVIDENCE:
{evidence or "No external evidence available."}

Determine:

1. The exact geographic destination.
2. The sovereign country containing that destination.
3. The ISO 3166-1 alpha-2 country code of that country.

Rules:

- Do not confuse a city with a state.
- Do not confuse a city with an airport.
- Do not confuse a city with a metropolitan area.
- Do not use state/province codes as country codes.
- Do not use airport codes.
- Do not use postal codes.
- Do not guess.
- Use the external evidence.
- If the country cannot be established confidently,
  leave country and country_code empty.

Return only structured output.
"""

    # ------------------------------------------------------------------
    # PROPERTY CARD VALIDATION
    # ------------------------------------------------------------------

    def _validate_property_cards(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> tuple[list[Issue], list[Recommendation], int]:
        """Validate property cards against the requested destination.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Issues, recommendations, and property-card score.
        """
        cards = getattr(
            content,
            "property_cards",
            [],
        )

        if not cards:
            return [], [], 100

        destination = self._resolve_destination(
            user_prompt
        )

        logger.info(
            "Resolved intended destination | destination=%s | "
            "country=%s | country_code=%s",
            destination.get("destination", ""),
            destination.get("country", ""),
            destination.get("country_code", ""),
        )

        valid_cards = []
        invalid_cards = []
        ambiguous_cards = []

        for index, card in enumerate(cards):
            decision = self._deterministic_card_match(
                card,
                destination,
            )

            logger.info(
                "Property card pre-validation | index=%d | "
                "title=%s | city=%s | country=%s | "
                "country_code=%s | decision=%s",
                index,
                getattr(card, "title", ""),
                getattr(card, "city", ""),
                getattr(card, "country", ""),
                getattr(card, "country_code", ""),
                decision,
            )

            if decision == "valid":
                valid_cards.append(
                    (index, card)
                )

            elif decision == "context_mismatch":
                invalid_cards.append(
                    (index, card)
                )

            else:
                ambiguous_cards.append(
                    (index, card)
                )

        logger.info(
            "Property card pre-validation completed | "
            "valid=%d | invalid=%d | ambiguous=%d",
            len(valid_cards),
            len(invalid_cards),
            len(ambiguous_cards),
        )

        issues = []
        recommendations = []

        for _, card in invalid_cards:
            issue, recommendation = (
                self._build_property_card_issue(
                    card,
                    "The property's country does not match "
                    "the country of the requested destination.",
                )
            )

            issues.append(issue)
            recommendations.append(
                recommendation
            )

        if ambiguous_cards:
            results = self._verify_ambiguous_cards_parallel(
                content=content,
                user_prompt=user_prompt,
                destination=destination,
                cards=ambiguous_cards,
            )

            for index, issue, recommendation in results:
                if issue:
                    issues.append(issue)

                if recommendation:
                    recommendations.append(
                        recommendation
                    )

                if not issue:
                    valid_cards.append(
                        (
                            index,
                            cards[index],
                        )
                    )

        total_cards = len(cards)
        valid_count = len(valid_cards)

        card_score = round(
            (valid_count / total_cards) * 100
        )

        logger.info(
            "Property card scoring | total=%d | "
            "valid=%d | invalid=%d | score=%d",
            total_cards,
            valid_count,
            total_cards - valid_count,
            card_score,
        )

        return (
            issues,
            recommendations,
            card_score,
        )

    @staticmethod
    def _deterministic_card_match(
        card,
        destination: dict[str, str],
    ) -> str:
        """Perform only safe deterministic geographic checks.

        Parameters:
            card: Property-card object.
            destination: Resolved intended destination.

        Returns:
            'valid', 'context_mismatch', or 'ambiguous'.
        """
        intended_country_code = (
            KnowledgeValidationEvaluator._normalize_country_code(
                destination.get("country_code", "")
            )
        )

        intended_destination = (
            KnowledgeValidationEvaluator._normalize_text(
                destination.get("destination", "")
            )
        )

        card_country_code = (
            KnowledgeValidationEvaluator._normalize_country_code(
                getattr(card, "country_code", "")
            )
        )

        card_country = (
            KnowledgeValidationEvaluator._normalize_text(
                getattr(card, "country", "")
            )
        )

        card_city = (
            KnowledgeValidationEvaluator._normalize_text(
                getattr(card, "city", "")
            )
        )

        card_location = (
            KnowledgeValidationEvaluator._normalize_text(
                getattr(card, "location", "")
            )
        )

        # Only compare country codes when both are actual
        # ISO-style country codes.
        if (
            intended_country_code
            and card_country_code
            and intended_country_code != card_country_code
        ):
            return "context_mismatch"

        # Do NOT compare raw country strings here.
        #
        # For example:
        #
        # United States != USA
        #
        # does NOT mean different countries.
        #
        # Country identity is resolved dynamically before
        # this method is reached when a country-code gate
        # is required.

        if intended_destination and card_city:
            if (
                intended_destination == card_city
                or card_city == intended_destination
            ):
                return "valid"

        if (
            intended_destination
            and card_location
            and intended_destination in card_location
        ):
            return "valid"

        return "ambiguous"

    def _verify_ambiguous_cards_parallel(
        self,
        content: WebsiteContent,
        user_prompt: str,
        destination: dict[str, str],
        cards: list[tuple[int, object]],
    ) -> list[
        tuple[
            int,
            Issue | None,
            Recommendation | None,
        ]
    ]:
        """Validate ambiguous property cards concurrently.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.
            destination: Intended destination.
            cards: Ambiguous property cards with indexes.

        Returns:
            Validation results for every ambiguous property card.
        """
        results = []

        with ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            future_map = {
                executor.submit(
                    self._verify_ambiguous_card,
                    content,
                    user_prompt,
                    destination,
                    index,
                    card,
                ): index
                for index, card in cards
            }

            for future in as_completed(
                future_map
            ):
                index = future_map[future]

                try:
                    issue, recommendation = (
                        future.result()
                    )
                except Exception:
                    logger.exception(
                        "Unexpected property-card validation "
                        "failure | index=%d",
                        index,
                    )

                    issue, recommendation = (
                        self._build_property_card_issue(
                            cards[
                                next(
                                    position
                                    for position, item in enumerate(cards)
                                    if item[0] == index
                                )
                            ][1],
                            "The geographic relationship "
                            "could not be verified.",
                        )
                    )

                results.append(
                    (
                        index,
                        issue,
                        recommendation,
                    )
                )

        return results

    def _verify_ambiguous_card(
        self,
        content: WebsiteContent,
        user_prompt: str,
        destination: dict[str, str],
        index: int,
        card,
    ) -> tuple[
        Issue | None,
        Recommendation | None,
    ]:
        """Verify ambiguous property geography using external evidence and LLM.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.
            destination: Intended destination.
            index: Property-card index.
            card: Property-card object.

        Returns:
            Issue and recommendation for a mismatch, otherwise None values.
        """
        card_country = self._normalize_text(
            getattr(card, "country", "")
        )

        card_country_code = (
            self._normalize_country_code(
                getattr(card, "country_code", "")
            )
        )

        card_country_identity = (
            self._resolve_country_identity(
                country=card_country,
                country_code=card_country_code,
                context=(
                    f"{getattr(card, 'city', '')}, "
                    f"{getattr(card, 'location', '')}"
                ),
            )
        )

        normalized_destination = dict(
            destination
        )

        if card_country_identity:
            normalized_card_country = (
                card_country_identity["country"]
            )

            normalized_card_country_code = (
                card_country_identity[
                    "country_code"
                ]
            )

            logger.info(
                "Property card country resolved | index=%d | "
                "original_country=%s | original_country_code=%s | "
                "canonical_country=%s | canonical_country_code=%s",
                index,
                card_country,
                card_country_code,
                normalized_card_country,
                normalized_card_country_code,
            )

            intended_country_code = (
                self._normalize_country_code(
                    normalized_destination.get(
                        "country_code",
                        "",
                    )
                )
            )

            if (
                intended_country_code
                and normalized_card_country_code
                and normalized_card_country_code
                != intended_country_code
            ):
                return self._build_property_card_issue(
                    card,
                    "The property's resolved country does not "
                    "match the country of the requested destination.",
                )

            normalized_destination[
                "country"
            ] = normalized_destination.get(
                "country",
                "",
            )

            normalized_destination[
                "country_code"
            ] = intended_country_code

        evidence = self._collect_single_card_evidence(
            content,
            index,
            card,
            normalized_destination,
        )

        structured_llm = self.llm.with_structured_output(
            PropertyCardValidationLLMResult
        )

        prompt = self._build_property_card_prompt(
            user_prompt=user_prompt,
            destination=normalized_destination,
            card=card,
            evidence=evidence,
        )

        try:
            result = structured_llm.invoke(
                prompt
            )
        except Exception:
            logger.exception(
                "Property card LLM validation failed | "
                "index=%d",
                index,
            )

            return self._build_property_card_issue(
                card,
                "The geographic relationship could not "
                "be verified.",
            )

        status = (
            str(result.status)
            .strip()
            .lower()
        )

        logger.info(
            "Property card LLM validation | index=%d | "
            "status=%s | reason=%s",
            index,
            status,
            result.reason,
        )

        if status == "valid":
            return None, None

        return self._build_property_card_issue(
            card,
            result.reason
            or (
                "The property's geographic relationship "
                "to the requested destination could not "
                "be established."
            ),
        )

    def _collect_single_card_evidence(
        self,
        content: WebsiteContent,
        index: int,
        card,
        destination: dict[str, str],
    ) -> str:
        """Collect geographic evidence for one property card.

        Parameters:
            content: Extracted webpage content.
            index: Property-card index.
            card: Property-card object.
            destination: Intended destination information.

        Returns:
            Formatted Tavily geographic evidence.
        """
        if not self.search_client:
            return ""

        query = self._build_card_search_query(
            card,
            destination,
        )

        if not query:
            return ""

        logger.info(
            "Tavily property-card search | index=%d | query=%s",
            index,
            query,
        )

        try:
            results = self.search_client.search(
                query=query,
                max_results=5,
            )
        except Exception:
            logger.exception(
                "Property-card Tavily search failed | index=%d",
                index,
            )
            return ""

        return self._format_search_results(
            results
        )

    @staticmethod
    def _build_card_search_query(
        card,
        destination: dict[str, str],
    ) -> str:
        """Build a dynamic geographic search query.

        Parameters:
            card: Property-card object.
            destination: Intended destination.

        Returns:
            Search query string.
        """
        values = [
            getattr(card, "title", ""),
            getattr(card, "city", ""),
            getattr(card, "country", ""),
            getattr(card, "country_code", ""),
            getattr(card, "location", ""),
            getattr(card, "property_type", ""),
            destination.get("destination", ""),
            destination.get("country", ""),
            destination.get("country_code", ""),
        ]

        query = " ".join(
            str(value).strip()
            for value in values
            if value
        )

        return query[:500]

    @staticmethod
    def _build_property_card_prompt(
        user_prompt: str,
        destination: dict[str, str],
        card,
        evidence: str,
    ) -> str:
        """Build the geographic property-card validation prompt.

        Parameters:
            user_prompt: Original webpage-generation prompt.
            destination: Intended destination.
            card: Property-card object.
            evidence: External geographic evidence.

        Returns:
            Property-card validation prompt.
        """
        return f"""
You are a STRICT geographic property-card validator.

Your ONLY responsibility is geographic destination validation.

USER PROMPT:
{user_prompt}

INTENDED DESTINATION:
{destination.get("destination", "")}

INTENDED COUNTRY:
{destination.get("country", "")}

INTENDED COUNTRY CODE:
{destination.get("country_code", "")}

PROPERTY:
Title: {getattr(card, "title", "")}
City: {getattr(card, "city", "")}
Country: {getattr(card, "country", "")}
Country Code: {getattr(card, "country_code", "")}
Location: {getattr(card, "location", "")}
Property Type: {getattr(card, "property_type", "")}

TAVILY GEOGRAPHIC EVIDENCE:
{evidence or "No external evidence available."}

Rules:

1. The USER PROMPT defines the intended destination.

2. Determine the property's actual physical location.

3. Country-name spelling and representation differences must NOT
   automatically mean different countries.

4. Treat country identity according to geographic evidence and
   ISO country identity, not raw string equality.

5. Examples such as USA and United States are illustrative
   representations of the same country. Resolve such equivalence
   dynamically from evidence.

6. A different country is always a context mismatch.

7. Same country does NOT automatically mean same destination.

8. Same state or province does NOT automatically mean same city.

9. Same metropolitan area does NOT automatically mean same city.

10. A neighboring municipality is not automatically part of
    the requested destination.

11. A suburb is not automatically part of the requested city.

12. An airport is not automatically part of the requested city.

13. Marketing language does not establish physical location.

14. Property titles must not override structured location data.

15. The property's City field must be evaluated independently.

16. If the property city is different from the intended destination,
    determine whether the property is physically inside the requested
    destination or merely nearby.

17. Metropolitan-area membership alone is insufficient.

18. Geographic proximity alone is insufficient.

19. If the property is physically inside the requested destination,
    return valid.

20. If the property is a separate municipality, city, town,
    jurisdiction, or surrounding location, return context_mismatch.

21. If reliable evidence establishes administrative membership
    inside the requested destination, return valid.

22. If reliable evidence establishes that the property is outside
    the requested destination, return context_mismatch.

23. If evidence is insufficient, return context_mismatch.

24. Do not broaden the requested destination.

25. Do not use property title or marketing terminology as proof
    of geographic membership.

26. Do not evaluate:
    - property quality
    - price
    - amenities
    - images
    - SEO
    - HTML
    - readability
    - writing style

Return only structured output.

status must be exactly:
valid
or
context_mismatch

If context_mismatch, provide a short concrete geographic reason.
"""

    # ------------------------------------------------------------------
    # ISSUE CREATION
    # ------------------------------------------------------------------

    @staticmethod
    def _build_property_card_issue(
        card,
        reason: str,
    ) -> tuple[Issue, Recommendation]:
        """Build an issue and recommendation for a geographic mismatch.

        Parameters:
            card: Property-card object.
            reason: Geographic mismatch explanation.

        Returns:
            Issue and recommendation pair.
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
                f"Review the '{title}' property card and remove "
                f"or replace it if it does not belong to the "
                f"destination specified by the user. "
                f"Detected location: '{location}'."
            ),
        )

        return issue, recommendation

    # ------------------------------------------------------------------
    # GENERAL SEARCH
    # ------------------------------------------------------------------

    def _collect_search_evidence(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> str:
        """Collect external evidence for general knowledge validation.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Formatted search evidence.
        """
        if not self.search_client:
            return ""

        query = self._build_search_query(
            content,
            user_prompt,
        )

        if not query:
            return ""

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
        return " ".join(
            part
            for part in [
                user_prompt,
                content.title,
            ]
            if part
        )[:400]

    @staticmethod
    def _format_search_results(
        results,
    ) -> str:
        """Format search results for LLM consumption.

        Parameters:
            results: Tavily search results.

        Returns:
            Formatted evidence string.
        """
        if not results:
            return ""

        evidence = []

        for index, result in enumerate(
            results,
            start=1,
        ):
            evidence.append(
                f"""
Result {index}
Title: {result.get("title", "")}
URL: {result.get("url", "")}
Snippet: {result.get("content", "")}
"""
            )

        return "\n".join(evidence)

    # ------------------------------------------------------------------
    # GENERAL KNOWLEDGE PROMPT
    # ------------------------------------------------------------------

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
            search_evidence: External search evidence.

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

USER PROMPT:
{user_prompt}

PAGE TITLE:
{content.title}

HEADINGS:
{headings}

WEBPAGE CONTENT:
{content.plain_text[:16000]}

SEARCH EVIDENCE:
{search_evidence or "No external evidence was found."}

Check:

1. Whether the content matches the destination and subject
   in the user prompt.

2. Incorrect factual claims.

3. Unsupported factual claims.

4. Contradictory claims.

5. Incorrect destination information.

6. Incorrect attraction or location information.

7. Incorrect travel information.

8. Incorrect hotel or property information.

9. Content belonging to another destination.

The USER PROMPT is authoritative for destination intent.

Do not treat webpage headings or title as authoritative
for destination identity.

Do not evaluate:

- SEO
- HTML
- keyword density
- readability
- writing style
- AI-generated writing style
- property-card images

If evidence is insufficient, classify the claim as uncertain.

Scoring:

100 = accurate and strongly aligned.
80-99 = minor issues.
60-79 = noticeable issues.
40-59 = significant issues.
0-39 = major inaccuracies or wrong destination.

Return only concrete findings.
"""

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        """Normalize text for comparison.

        Parameters:
            value: Text to normalize.

        Returns:
            Lowercase normalized text.
        """
        value = str(
            value or ""
        ).lower()

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

    @staticmethod
    def _normalize_country_code(
        value: str,
    ) -> str:
        """Normalize an ISO country code.

        Parameters:
            value: Candidate country code.

        Returns:
            Uppercase two-letter code or empty string.
        """
        value = str(
            value or ""
        ).strip().upper()

        return (
            value
            if re.fullmatch(
                r"[A-Z]{2}",
                value,
            )
            else ""
        )

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






# import logging
# import re
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
#     """Represents validation output for general webpage knowledge.

#     Parameters:
#         status: Validation status of the claim.
#         claim: Factual claim being evaluated.
#         evidence: Supporting evidence.
#         location: Claim location on the webpage.
#         explanation: Explanation of the validation decision.

#     Returns:
#         Structured claim-validation information.
#     """

#     status: str = Field(description="verified, unsupported, or uncertain")
#     claim: str = ""
#     evidence: str = ""
#     location: str = ""
#     explanation: str = ""


# class DestinationResolutionLLMResult(BaseModel):
#     """Represents the resolved destination from the user prompt.

#     Parameters:
#         destination: Primary destination requested by the user.
#         country: Country containing the destination.
#         country_code: ISO 3166-1 alpha-2 country code.
#         explanation: Explanation of the resolution.

#     Returns:
#         Structured destination-resolution information.
#     """

#     destination: str = ""
#     country: str = ""
#     country_code: str = ""
#     explanation: str = ""


# class PropertyCardValidationLLMResult(BaseModel):
#     """Represents geographic validation of one property card.

#     Parameters:
#         status: Geographic validation status.
#         reason: Explanation for the decision.

#     Returns:
#         Structured property-card validation result.
#     """

#     status: str = Field(description="valid or context_mismatch")
#     reason: str = ""


# class KnowledgeValidationLLMResult(BaseModel):
#     """Represents the general knowledge-validation result.

#     Parameters:
#         score: Knowledge-validation score from 0 to 100.
#         verified_claims: Supported factual claims.
#         unsupported_claims: Unsupported factual claims.
#         uncertain_claims: Claims requiring more evidence.
#         issues: Concrete knowledge issues.
#         recommendations: Recommended corrections.

#     Returns:
#         Structured knowledge-validation result.
#     """

#     score: int = Field(ge=0, le=100)
#     verified_claims: list[str] = Field(default_factory=list)
#     unsupported_claims: list[str] = Field(default_factory=list)
#     uncertain_claims: list[str] = Field(default_factory=list)
#     issues: list[str] = Field(default_factory=list)
#     recommendations: list[str] = Field(default_factory=list)


# class KnowledgeValidationEvaluator:
#     """Validates webpage knowledge and property-card geographic relevance.

#     Parameters:
#         llm: Language model used for structured validation.
#         search_client: Tavily-compatible search client.
#         max_workers: Number of workers used for external searches.

#     Returns:
#         Evaluator capable of validating webpage knowledge and property cards.
#     """

#     def __init__(self, llm, search_client, max_workers: int = 4):
#         self.llm = llm
#         self.search_client = search_client
#         self.max_workers = max_workers

#     def evaluate(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#     ) -> KnowledgeValidationResult:
#         """Evaluate webpage knowledge against the original user prompt.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             KnowledgeValidationResult containing validation findings.
#         """
#         logger.info(
#             "Knowledge validation started | user_prompt=%s",
#             user_prompt[:300],
#         )

#         general_result = self._analyze(content, user_prompt)

#         issues = [
#             Issue(
#                 severity=self._issue_severity(general_result.score),
#                 title="Knowledge Validation",
#                 description=issue,
#             )
#             for issue in general_result.issues
#         ]

#         recommendations = [
#             Recommendation(
#                 title="Fix Knowledge Issue",
#                 description=recommendation,
#             )
#             for recommendation in general_result.recommendations
#         ]

#         card_issues, card_recommendations, card_score = (
#             self._validate_property_cards(content, user_prompt)
#         )

#         issues.extend(card_issues)
#         recommendations.extend(card_recommendations)

#         if getattr(content, "property_cards", []):
#             score = min(general_result.score, card_score)
#         else:
#             score = general_result.score

#         logger.info(
#             "Knowledge validation completed | base_score=%d | "
#             "card_score=%d | final_score=%d",
#             general_result.score,
#             card_score,
#             score,
#         )

#         return KnowledgeValidationResult(
#             score=score,
#             issues=issues,
#             recommendations=recommendations,
#             verified_claims=general_result.verified_claims,
#             unsupported_claims=general_result.unsupported_claims,
#             uncertain_claims=general_result.uncertain_claims,
#         )

#     # ------------------------------------------------------------------
#     # GENERAL KNOWLEDGE VALIDATION
#     # ------------------------------------------------------------------

#     def _analyze(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#     ) -> KnowledgeValidationLLMResult:
#         """Validate general webpage claims against user intent.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Structured general knowledge-validation result.
#         """
#         search_evidence = self._collect_search_evidence(
#             content,
#             user_prompt,
#         )

#         structured_llm = self.llm.with_structured_output(
#             KnowledgeValidationLLMResult
#         )

#         result = structured_llm.invoke(
#             self._build_prompt(
#                 content=content,
#                 user_prompt=user_prompt,
#                 search_evidence=search_evidence,
#             )
#         )

#         logger.info("General knowledge validation LLM call successful.")

#         return result

#     # ------------------------------------------------------------------
#     # DESTINATION RESOLUTION
#     # ------------------------------------------------------------------

#     def _resolve_destination(
#         self,
#         user_prompt: str,
#     ) -> dict[str, str]:
#         """Resolve destination geography from the user prompt.

#         Parameters:
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Dictionary containing destination and geographic metadata.
#         """
#         structured_llm = self.llm.with_structured_output(
#             DestinationResolutionLLMResult
#         )

#         try:
#             extracted = structured_llm.invoke(
#                 self._build_destination_prompt(user_prompt)
#             )
#         except Exception:
#             logger.exception("Destination extraction failed.")
#             return {}

#         destination = self._normalize_text(extracted.destination)
#         country = self._normalize_text(extracted.country)
#         country_code = self._normalize_country_code(
#             extracted.country_code
#         )

#         if not destination:
#             return {}

#         logger.info(
#             "Destination extracted | destination=%s | country=%s | "
#             "country_code=%s",
#             destination,
#             country,
#             country_code,
#         )

#         if not country or not country_code:
#             evidence = self._resolve_destination_with_search(
#                 extracted.destination
#             )

#             if evidence:
#                 try:
#                     resolved = structured_llm.invoke(
#                         self._build_destination_resolution_prompt(
#                             user_prompt=user_prompt,
#                             destination=extracted.destination,
#                             evidence=evidence,
#                         )
#                     )

#                     resolved_destination = self._normalize_text(
#                         resolved.destination
#                     )
#                     resolved_country = self._normalize_text(
#                         resolved.country
#                     )
#                     resolved_code = self._normalize_country_code(
#                         resolved.country_code
#                     )

#                     if resolved_destination:
#                         destination = resolved_destination

#                     if resolved_country:
#                         country = resolved_country

#                     if resolved_code:
#                         country_code = resolved_code

#                 except Exception:
#                     logger.exception(
#                         "Destination geographic resolution failed."
#                     )

#         logger.info(
#             "Resolved intended destination | destination=%s | "
#             "country=%s | country_code=%s",
#             destination,
#             country,
#             country_code,
#         )

#         return {
#             "destination": destination,
#             "country": country,
#             "country_code": country_code,
#         }

#     def _resolve_destination_with_search(
#         self,
#         destination: str,
#     ) -> str:
#         """Search external sources to resolve destination geography.

#         Parameters:
#             destination: Destination extracted from the user prompt.

#         Returns:
#             Formatted external geographic evidence.
#         """
#         if not self.search_client or not destination:
#             return ""

#         query = (
#             f'"{destination}" geographic location country '
#             f'official municipality'
#         )

#         try:
#             results = self.search_client.search(
#                 query=query,
#                 max_results=5,
#             )
#         except Exception:
#             logger.exception(
#                 "Destination Tavily search failed."
#             )
#             return ""

#         return self._format_search_results(results)

#     @staticmethod
#     def _build_destination_prompt(
#         user_prompt: str,
#     ) -> str:
#         """Build the destination extraction prompt.

#         Parameters:
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Destination extraction prompt.
#         """
#         return f"""
# You are a geographic destination extraction system.

# USER PROMPT:
# {user_prompt}

# Extract the PRIMARY geographic destination that the requested webpage
# is supposed to be about.

# Return:
# - destination
# - country
# - country_code
# - explanation

# STRICT RULES:

# 1. The USER PROMPT is the only authority for destination intent.

# 2. Ignore webpage titles, headings, property cards, hotel names,
#    property locations, and webpage content.

# 3. Extract the destination the user actually requested.

# 4. The destination may be a city, municipality, country, state,
#    region, island, or other geographic area.

# 5. The country must be the actual sovereign country containing
#    the destination.

# 6. country_code must be the ISO 3166-1 alpha-2 code of that country.

# 7. NEVER return:
#    - state codes
#    - province codes
#    - city codes
#    - airport codes
#    - postal codes
#    - regional abbreviations
#    - marketing abbreviations

# 8. The country_code must correspond to the COUNTRY, not the destination.

# 9. If the country is not explicitly stated but the destination is
#    geographically unambiguous, the country may be resolved.

# 10. If the country cannot be resolved confidently, return empty
#     country and country_code.

# 11. Never guess a country code from letters appearing in the
#     destination name.

# 12. Internally verify:

#     destination -> country -> ISO 3166-1 alpha-2 country_code

# 13. Example:

#     destination = New York City
#     country = United States
#     country_code = US

# 14. Return only structured output.
# """

#     @staticmethod
#     def _build_destination_resolution_prompt(
#         user_prompt: str,
#         destination: str,
#         evidence: str,
#     ) -> str:
#         """Build the geographic destination resolution prompt.

#         Parameters:
#             user_prompt: Original webpage-generation prompt.
#             destination: Extracted destination.
#             evidence: External geographic evidence.

#         Returns:
#             Geographic resolution prompt.
#         """
#         return f"""
# You are resolving the geographic identity of a destination.

# USER PROMPT:
# {user_prompt}

# DESTINATION:
# {destination}

# EXTERNAL GEOGRAPHIC EVIDENCE:
# {evidence or "No external evidence available."}

# Determine:

# 1. The exact geographic destination.
# 2. The sovereign country containing that destination.
# 3. The ISO 3166-1 alpha-2 country code of that country.

# STRICT RULES:

# - Do not confuse a city with its state.
# - Do not confuse a city with an airport.
# - Do not confuse a city with a metropolitan area.
# - Do not use state/province codes as country codes.
# - Do not use airport codes.
# - Do not use postal codes.
# - Do not guess.
# - country_code MUST correspond to country.
# - Use the external evidence.
# - If the country cannot be established confidently,
#   leave country and country_code empty.

# Return only structured output.
# """

#     # ------------------------------------------------------------------
#     # PROPERTY CARD VALIDATION
#     # ------------------------------------------------------------------

#     def _validate_property_cards(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#     ) -> tuple[list[Issue], list[Recommendation], int]:
#         """Validate property cards against the requested destination.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Issues, recommendations, and property-card score.
#         """
#         cards = getattr(content, "property_cards", [])

#         if not cards:
#             return [], [], 100

#         destination = self._resolve_destination(user_prompt)

#         logger.info(
#             "Resolved intended destination | destination=%s | "
#             "country=%s | country_code=%s",
#             destination.get("destination", ""),
#             destination.get("country", ""),
#             destination.get("country_code", ""),
#         )

#         valid_cards = []
#         invalid_cards = []
#         ambiguous_cards = []

#         for index, card in enumerate(cards):
#             decision = self._deterministic_card_match(
#                 card,
#                 destination,
#             )

#             logger.info(
#                 "Property card pre-validation | index=%d | "
#                 "title=%s | city=%s | country=%s | "
#                 "location=%s | decision=%s",
#                 index,
#                 getattr(card, "title", ""),
#                 getattr(card, "city", ""),
#                 getattr(card, "country", ""),
#                 getattr(card, "location", ""),
#                 decision,
#             )

#             if decision == "valid":
#                 valid_cards.append((index, card))

#             elif decision == "context_mismatch":
#                 invalid_cards.append((index, card))

#             else:
#                 ambiguous_cards.append((index, card))

#         logger.info(
#             "Property card pre-validation completed | "
#             "valid=%d | invalid=%d | ambiguous=%d",
#             len(valid_cards),
#             len(invalid_cards),
#             len(ambiguous_cards),
#         )

#         issues = []
#         recommendations = []

#         for _, card in invalid_cards:
#             issue, recommendation = self._build_property_card_issue(
#                 card,
#                 "The property's country does not match the country "
#                 "of the requested destination.",
#             )

#             issues.append(issue)
#             recommendations.append(recommendation)

#         results = []

#         if ambiguous_cards:
#             results = self._verify_ambiguous_cards_parallel(
#                 content=content,
#                 user_prompt=user_prompt,
#                 destination=destination,
#                 cards=ambiguous_cards,
#             )

#             for issue, recommendation in results:
#                 if issue:
#                     issues.append(issue)

#                 if recommendation:
#                     recommendations.append(recommendation)

#                 if not issue:
#                     valid_cards.append((0, None))

#         total_cards = len(cards)

#         invalid_count = len(invalid_cards) + sum(
#             1
#             for issue, _ in results
#             if issue
#         ) if ambiguous_cards else len(invalid_cards)

#         valid_count = total_cards - invalid_count

#         card_score = round(
#             (valid_count / total_cards) * 100
#         )

#         logger.info(
#             "Property card scoring | total=%d | valid=%d | "
#             "invalid=%d | score=%d",
#             total_cards,
#             valid_count,
#             invalid_count,
#             card_score,
#         )

#         return issues, recommendations, card_score

#     def _verify_ambiguous_cards_parallel(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#         destination: dict[str, str],
#         cards: list[tuple[int, object]],
#     ) -> list[tuple[Issue | None, Recommendation | None]]:
#         """Validate ambiguous property cards concurrently.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.
#             destination: Intended destination.
#             cards: Ambiguous property-card collection.

#         Returns:
#             Ordered validation results for each ambiguous card.
#         """
#         results = [None] * len(cards)

#         with ThreadPoolExecutor(
#             max_workers=self.max_workers
#         ) as executor:
#             futures = {
#                 executor.submit(
#                     self._verify_ambiguous_card,
#                     content,
#                     user_prompt,
#                     destination,
#                     index,
#                     card,
#                 ): position
#                 for position, (index, card) in enumerate(cards)
#             }

#             for future in as_completed(futures):
#                 position = futures[future]

#                 try:
#                     results[position] = future.result()
#                 except Exception:
#                     logger.exception(
#                         "Unexpected property-card validation failure | "
#                         "position=%d",
#                         position,
#                     )

#                     index, card = cards[position]

#                     results[position] = (
#                         *self._build_property_card_issue(
#                             card,
#                             "The geographic relationship could not "
#                             "be verified.",
#                         ),
#                     )

#         return results

#     @staticmethod
#     def _deterministic_card_match(
#         card,
#         destination: dict[str, str],
#     ) -> str:
#         """Perform only safe deterministic geographic checks.

#         Uses ISO 3166-1 alpha-2 country codes for comparison whenever
#         both the intended destination and the property card have one,
#         since codes are canonical and unambiguous (no reliance on
#         matching country-name strings/variants such as "USA" vs
#         "United States"). If a reliable country code is not available
#         on either side, no deterministic country decision is made and
#         the card is deferred to the LLM/Tavily-based ambiguous-card
#         verification instead of being guessed at here.

#         Parameters:
#             card: Property-card object.
#             destination: Resolved intended destination.

#         Returns:
#             'valid', 'context_mismatch', or 'ambiguous'.
#         """
#         intended_country_code = (
#             KnowledgeValidationEvaluator._normalize_country_code(
#                 destination.get("country_code", "")
#             )
#         )

#         card_country_code = (
#             KnowledgeValidationEvaluator._normalize_country_code(
#                 getattr(card, "country_code", "")
#             )
#         )

#         intended_destination = KnowledgeValidationEvaluator._normalize_text(
#             destination.get("destination", "")
#         )

#         card_city = KnowledgeValidationEvaluator._normalize_text(
#             getattr(card, "city", "")
#         )

#         if intended_country_code and card_country_code:
#             if intended_country_code != card_country_code:
#                 return "context_mismatch"

#             if (
#                 intended_destination
#                 and card_city
#                 and intended_destination == card_city
#             ):
#                 return "valid"

#             return "ambiguous"

#         # No reliable country code on one or both sides. Do not attempt
#         # a deterministic country-name string match here, since name
#         # variants cannot be reliably compared with plain equality.
#         # Defer entirely to LLM/Tavily-based verification.
#         return "ambiguous"

#     def _verify_ambiguous_card(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#         destination: dict[str, str],
#         index: int,
#         card,
#     ) -> tuple[Issue | None, Recommendation | None]:
#         """Verify ambiguous property geography using Tavily and LLM.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.
#             destination: Intended destination.
#             index: Property-card index.
#             card: Property-card object.

#         Returns:
#             Issue and recommendation pair.
#         """
#         evidence = self._collect_single_card_evidence(
#             content=content,
#             index=index,
#             card=card,
#             destination=destination,
#         )

#         structured_llm = self.llm.with_structured_output(
#             PropertyCardValidationLLMResult
#         )

#         prompt = self._build_property_card_prompt(
#             user_prompt=user_prompt,
#             destination=destination,
#             card=card,
#             evidence=evidence,
#         )

#         try:
#             result = structured_llm.invoke(prompt)
#         except Exception:
#             logger.exception(
#                 "Property card LLM validation failed | index=%d",
#                 index,
#             )

#             issue, recommendation = self._build_property_card_issue(
#                 card,
#                 "The geographic relationship could not be verified.",
#             )

#             return issue, recommendation

#         status = result.status.strip().lower()

#         logger.info(
#             "Property card LLM validation | index=%d | "
#             "status=%s | reason=%s",
#             index,
#             status,
#             result.reason,
#         )

#         if status == "valid":
#             return None, None

#         issue, recommendation = self._build_property_card_issue(
#             card,
#             result.reason
#             or (
#                 "The property's physical location could not be "
#                 "established as belonging to the requested destination."
#             ),
#         )

#         return issue, recommendation

#     def _collect_single_card_evidence(
#         self,
#         content: WebsiteContent,
#         index: int,
#         card,
#         destination: dict[str, str],
#     ) -> str:
#         """Collect geographic evidence about the destination and property city.

#         Parameters:
#             content: Extracted webpage content.
#             index: Property-card index.
#             card: Property-card object.
#             destination: Intended destination.

#         Returns:
#             Formatted Tavily geographic evidence.
#         """
#         if not self.search_client:
#             return ""

#         query = self._build_card_search_query(
#             card=card,
#             destination=destination,
#         )

#         if not query:
#             return ""

#         logger.info(
#             "Tavily property-card geographic search | "
#             "index=%d | query=%s",
#             index,
#             query,
#         )

#         try:
#             results = self.search_client.search(
#                 query=query,
#                 max_results=5,
#             )
#         except Exception:
#             logger.exception(
#                 "Property-card Tavily search failed | index=%d",
#                 index,
#             )
#             return ""

#         return self._format_search_results(results)

#     @staticmethod
#     def _build_card_search_query(
#         card,
#         destination: dict[str, str],
#     ) -> str:
#         """Build a dynamic geographic relationship search query.

#         Parameters:
#             card: Property-card object.
#             destination: Intended destination.

#         Returns:
#             Search query focused on the geographic relationship.
#         """
#         intended_destination = str(
#             destination.get("destination", "")
#         ).strip()

#         intended_country = str(
#             destination.get("country", "")
#         ).strip()

#         property_city = str(
#             getattr(card, "city", "")
#         ).strip()

#         property_country = str(
#             getattr(card, "country", "")
#         ).strip()

#         property_location = str(
#             getattr(card, "location", "")
#         ).strip()

#         if not intended_destination or not property_city:
#             return ""

#         query_parts = [
#             f'"{property_city}"',
#             f'"{intended_destination}"',
#             "geographic relationship",
#             "municipality city location",
#         ]

#         if intended_country:
#             query_parts.append(
#                 f'"{intended_country}"'
#             )

#         if property_country:
#             query_parts.append(
#                 f'"{property_country}"'
#             )

#         if property_location:
#             query_parts.append(
#                 f'"{property_location}"'
#             )

#         return " ".join(query_parts)[:700]

#     @staticmethod
#     def _build_property_card_prompt(
#         user_prompt: str,
#         destination: dict[str, str],
#         card,
#         evidence: str,
#     ) -> str:
#         """Build a strict geographic property-card validation prompt.

#         Parameters:
#             user_prompt: Original webpage-generation prompt.
#             destination: Intended destination.
#             card: Property-card object.
#             evidence: External geographic evidence.

#         Returns:
#             Property-card validation prompt.
#         """
#         return f"""
# You are a STRICT geographic property-card validator.

# Your ONLY task is to determine whether the property's ACTUAL PHYSICAL
# LOCATION belongs to the EXACT INTENDED DESTINATION requested by the user.

# USER PROMPT:
# {user_prompt}

# INTENDED DESTINATION:
# {destination.get("destination", "")}

# INTENDED COUNTRY:
# {destination.get("country", "")}

# INTENDED COUNTRY CODE:
# {destination.get("country_code", "")}

# PROPERTY:
# Title: {getattr(card, "title", "")}
# City: {getattr(card, "city", "")}
# Country: {getattr(card, "country", "")}
# Country Code: {getattr(card, "country_code", "")}
# Location: {getattr(card, "location", "")}
# Property Type: {getattr(card, "property_type", "")}

# TAVILY GEOGRAPHIC EVIDENCE:
# {evidence or "No external geographic evidence available."}

# TASK:

# Determine whether the PROPERTY'S ACTUAL PHYSICAL LOCATION belongs
# geographically and administratively to the INTENDED DESTINATION.

# STRICT RULES:

# 1. The USER PROMPT is the only authority for the intended destination.

# 2. Never use the webpage title or webpage headings to redefine
#    the intended destination.

# 3. Never use the property title as proof of geographic membership.

# 4. The property's structured geographic fields are the primary
#    property-location evidence.

# 5. The PROPERTY CITY is especially important.

# 6. A different country is always context_mismatch.

# 7. Being in the same country does NOT establish validity.

# 8. Being in the same state or province does NOT establish validity.

# 9. Being in the same region does NOT establish validity.

# 10. Being in the same metropolitan area does NOT establish validity.

# 11. Being geographically close does NOT establish validity.

# 12. Being commonly associated with the destination does NOT establish
#     validity.

# 13. A separate municipality, city, town, borough, district, county,
#     state, province, or jurisdiction must not automatically be treated
#     as part of the intended destination.

# 14. A neighborhood, borough, district, subdivision, or subcity MAY be
#     valid when it is actually geographically or administratively
#     contained within the intended destination.

# 15. Do not assume that a place is inside the intended destination.
#     Establish the geographic relationship using the supplied
#     structured location and external evidence.

# 16. If the property city and intended destination have different names,
#     do NOT automatically return context_mismatch.

# 17. If the property city is a subdivision, neighborhood, borough,
#     district, municipality, or other geographic subdivision that is
#     actually inside the intended destination, return valid.

# 18. If the property city is a separate city or municipality outside
#     the intended destination, return context_mismatch.

# 19. Metropolitan-area membership is never sufficient.

# 20. Airport proximity or airport association is never sufficient.

# 21. Hotel/property marketing language is never sufficient.

# 22. Tavily evidence must be used to determine the geographic
#     relationship between the PROPERTY CITY and INTENDED DESTINATION.

# 23. Search evidence about the property itself is useful only when it
#     establishes the property's physical location.

# 24. Search evidence about the destination itself is useful only when
#     it establishes the destination's geographic boundary or hierarchy.

# 25. Do not simply search for matching words.

# 26. If evidence establishes that the property city is inside the
#     intended destination, return valid.

# 27. If evidence establishes that the property city is a separate
#     municipality/city outside the intended destination, return
#     context_mismatch.

# 28. If the property city is a valid subdivision of the intended
#     destination, return valid.

# 29. If the property city is merely nearby, return context_mismatch.

# 30. If the property city is merely part of the same metropolitan area,
#     return context_mismatch.

# 31. If the property is in a surrounding city or suburb that is not
#     geographically inside the intended destination, return
#     context_mismatch.

# 32. If the evidence is insufficient to establish that the property
#     physically belongs to the intended destination, return
#     context_mismatch.

# 33. Do not broaden or reinterpret the intended destination.

# 34. Do not evaluate:
#     - property quality
#     - property images
#     - SEO
#     - HTML
#     - readability
#     - writing style
#     - AI-generated writing style
#     - price
#     - amenities
#     - hotel quality

# GEOGRAPHIC DECISION PROCESS:

# Step 1:
# Identify the intended destination from the USER PROMPT.

# Step 2:
# Identify the property's actual city/municipality from the structured
# PROPERTY fields.

# Step 3:
# Confirm the property's country.

# Step 4:
# Determine the geographic relationship between the property city and
# the intended destination.

# Step 5:
# Distinguish between:
# - exact destination
# - subdivision inside destination
# - separate municipality
# - neighboring city
# - suburb outside destination
# - metropolitan-area location
# - same-state location
# - same-country location

# Step 6:
# Use Tavily evidence to resolve the relationship when it is not obvious.

# Step 7:
# Return valid only when the physical location belongs to the intended
# destination.

# FINAL OUTPUT:

# Return ONLY:

# status=valid

# OR

# status=context_mismatch

# If context_mismatch, provide a short concrete geographic reason.
# """

#     # ------------------------------------------------------------------
#     # ISSUE CREATION
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _build_property_card_issue(
#         card,
#         reason: str,
#     ) -> tuple[Issue, Recommendation]:
#         """Build an issue and recommendation for a geographic mismatch.

#         Parameters:
#             card: Property-card object.
#             reason: Geographic mismatch explanation.

#         Returns:
#             Issue and recommendation pair.
#         """
#         title = getattr(
#             card,
#             "title",
#             "Unknown property",
#         )

#         location = getattr(
#             card,
#             "location",
#             "",
#         )

#         description = (
#             f"The property card '{title}'"
#         )

#         if location:
#             description += (
#                 f" is associated with {location}."
#             )

#         if reason:
#             description += f" {reason}"

#         issue = Issue(
#             severity="High",
#             title="Property Card Context Mismatch",
#             description=description,
#         )

#         recommendation = Recommendation(
#             title="Review Property Card",
#             description=(
#                 f"Review the '{title}' property card and remove or "
#                 f"replace it if it does not belong to the destination "
#                 f"specified by the user. Detected location: "
#                 f"'{location}'."
#             ),
#         )

#         return issue, recommendation

#     # ------------------------------------------------------------------
#     # GENERAL SEARCH
#     # ------------------------------------------------------------------

#     def _collect_search_evidence(
#         self,
#         content: WebsiteContent,
#         user_prompt: str,
#     ) -> str:
#         """Collect Tavily evidence for general knowledge validation.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Formatted search evidence.
#         """
#         if not self.search_client:
#             return ""

#         query = self._build_search_query(
#             content,
#             user_prompt,
#         )

#         if not query:
#             return ""

#         try:
#             results = self.search_client.search(
#                 query=query,
#                 max_results=5,
#             )
#         except Exception:
#             logger.exception(
#                 "General Tavily search failed."
#             )
#             return ""

#         return self._format_search_results(results)

#     @staticmethod
#     def _build_search_query(
#         content: WebsiteContent,
#         user_prompt: str,
#     ) -> str:
#         """Build the general knowledge search query.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.

#         Returns:
#             Search query string.
#         """
#         return " ".join(
#             part
#             for part in [
#                 user_prompt,
#                 content.title,
#             ]
#             if part
#         )[:400]

#     @staticmethod
#     def _format_search_results(results) -> str:
#         """Format Tavily results for LLM consumption.

#         Parameters:
#             results: Tavily search results.

#         Returns:
#             Formatted search evidence.
#         """
#         if not results:
#             return ""

#         evidence = []

#         for index, result in enumerate(
#             results,
#             start=1,
#         ):
#             evidence.append(
#                 f"""
# Result {index}
# Title: {result.get("title", "")}
# URL: {result.get("url", "")}
# Snippet: {result.get("content", "")}
# """
#             )

#         return "\n".join(evidence)

#     # ------------------------------------------------------------------
#     # GENERAL KNOWLEDGE PROMPT
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _build_prompt(
#         content: WebsiteContent,
#         user_prompt: str,
#         search_evidence: str = "",
#     ) -> str:
#         """Build the general knowledge-validation prompt.

#         Parameters:
#             content: Extracted webpage content.
#             user_prompt: Original webpage-generation prompt.
#             search_evidence: External search evidence.

#         Returns:
#             Knowledge-validation prompt.
#         """
#         headings = [
#             heading
#             for heading_list in (
#                 content.headings.h1,
#                 content.headings.h2,
#                 content.headings.h3,
#                 content.headings.h4,
#             )
#             for heading in heading_list
#         ]

#         return f"""
# You are a factual-content validator for an AI-generated travel webpage.

# Your ONLY responsibility is KNOWLEDGE VALIDATION.

# USER PROMPT:
# {user_prompt}

# PAGE TITLE:
# {content.title}

# HEADINGS:
# {headings}

# WEBPAGE CONTENT:
# {content.plain_text[:16000]}

# SEARCH EVIDENCE:
# {search_evidence or "No external evidence was found."}

# Check:

# 1. Whether the content matches the destination and subject in the
#    user prompt.

# 2. Incorrect factual claims.

# 3. Unsupported factual claims.

# 4. Contradictory claims.

# 5. Incorrect destination information.

# 6. Incorrect attraction or location information.

# 7. Incorrect travel information.

# 8. Incorrect hotel or property information.

# 9. Content belonging to another destination.

# The USER PROMPT is authoritative for destination intent.

# Do not treat webpage headings or title as authoritative for destination
# identity.

# Do not evaluate:

# - SEO
# - HTML
# - keyword density
# - readability
# - writing style
# - AI-generated writing style
# - property-card images

# If evidence is insufficient, classify the claim as uncertain.

# Scoring:

# 100 = accurate and strongly aligned.
# 80-99 = minor issues.
# 60-79 = noticeable issues.
# 40-59 = significant issues.
# 0-39 = major inaccuracies or wrong destination.

# Return only concrete findings.
# """

#     # ------------------------------------------------------------------
#     # HELPERS
#     # ------------------------------------------------------------------

#     @staticmethod
#     def _normalize_text(
#         value: str,
#     ) -> str:
#         """Normalize geographic text for comparison.

#         Parameters:
#             value: Text to normalize.

#         Returns:
#             Lowercase normalized text.
#         """
#         value = str(value or "").lower()

#         value = re.sub(
#             r"[^a-z0-9\s]",
#             " ",
#             value,
#         )

#         value = re.sub(
#             r"\s+",
#             " ",
#             value,
#         )

#         return value.strip()

#     @staticmethod
#     def _normalize_country_code(
#         value: str,
#     ) -> str:
#         """Normalize a country code.

#         Parameters:
#             value: Country code.

#         Returns:
#             Uppercase two-letter code.
#         """
#         value = str(value or "").strip().upper()

#         if not re.fullmatch(
#             r"[A-Z]{2}",
#             value,
#         ):
#             return ""

#         return value

#     @staticmethod
#     def _same_geographic_name(
#         first: str,
#         second: str,
#     ) -> bool:
#         """Compare two normalized geographic names.

#         Parameters:
#             first: First geographic name.
#             second: Second geographic name.

#         Returns:
#             True when the names represent the same normalized text.
#         """
#         first = KnowledgeValidationEvaluator._normalize_text(first)
#         second = KnowledgeValidationEvaluator._normalize_text(second)

#         if not first or not second:
#             return False

#         return first == second

#     @staticmethod
#     def _issue_severity(
#         score: int,
#     ) -> str:
#         """Convert a numerical score into an issue severity.

#         Parameters:
#             score: Knowledge-validation score.

#         Returns:
#             High, Medium, or Low severity.
#         """
#         if score < 40:
#             return "High"

#         if score < 70:
#             return "Medium"

#         return "Low"