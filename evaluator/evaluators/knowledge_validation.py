import base64
import logging
import mimetypes
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import requests
from google import genai
from google.genai import types
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


class HeroImageValidationItem(BaseModel):
    """Represents validation of one hero-section image.

    Parameters:
        image_index: Position of the image in the hero-image collection.
        status: Geographic compatibility of the image.
        detected_location: Location the image appears to represent.
        reason: Explanation for the validation decision.

    Returns:
        Structured hero-image validation information.
    """

    image_index: int = Field( description="Zero-based index of the hero image.")

    status: str = Field( description="valid, context_mismatch, or uncertain")

    detected_location: str = ""

    reason: str = ""


class HeroImageValidationLLMResult(BaseModel):
    """Represents validation results for all hero-section images.

    Parameters:
        results: Validation result for every submitted hero image.

    Returns:
        Structured hero-image validation result.
    """

    results: list[HeroImageValidationItem] = Field(
        default_factory=list
    )

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

    def __init__(self, llm, search_client,  gemini_client=None,
    gemini_model: str = "gemini-3.1-flash-lite", max_workers: int = 4):

        self.llm = llm
        self.search_client = search_client
        self.gemini_client = gemini_client
        self.gemini_model = gemini_model
        self.max_workers = max_workers

        logger.info(
            "KnowledgeValidationEvaluator initialized | "
            "llm=%s | search_client=%s | gemini_enabled=%s | "
            "gemini_model=%s | max_workers=%d",
            type(llm).__name__,
            type(search_client).__name__,
            bool(gemini_client),
            gemini_model,
            max_workers,
        )

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

        image_issues, image_recommendations, image_score = (
            self._validate_hero_images(
                content=content,
                user_prompt=user_prompt,
            )
        )

        issues.extend(image_issues)
        recommendations.extend(image_recommendations)

        card_issues, card_recommendations, card_score = (
            self._validate_property_cards(
                content,
                user_prompt,
            )
        )

        issues.extend(card_issues)
        recommendations.extend(card_recommendations)

        scores = [general_result.score]

        if getattr(content, "property_cards", []):
            scores.append(card_score)

        if self._has_hero_images(content):
            scores.append(image_score)

        score = min(scores)

        logger.info(
            "Knowledge validation completed | "
            "general_score=%d | card_score=%d | "
            "image_score=%d | final_score=%d",
            general_result.score,
            card_score,
            image_score,
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
        
        if country_code:
            return {"country": country, "country_code": country_code}

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
    # HERO IMAGE VALIDATION
    # ------------------------------------------------------------------

    def _has_hero_images(
        self,
        content: WebsiteContent,
    ) -> bool:
        """Return whether hero-section images are available.

        The extractor may expose hero images explicitly as `hero_images`.
        When that field is unavailable, no image validation is attempted.

        Parameters:
            content: Extracted webpage content.

        Returns:
            True when at least one hero image exists.
        """
        return bool(
            getattr(content, "hero_images", None)
        )

    def _validate_hero_images(
        self,
        content: WebsiteContent,
        user_prompt: str,
    ) -> tuple[
        list[Issue],
        list[Recommendation],
        int,
    ]:
        """Validate hero images against the destination from the user prompt.

        Parameters:
            content: Extracted webpage content.
            user_prompt: Original webpage-generation prompt.

        Returns:
            Issues, recommendations, and hero-image score.
        """
        hero_images = getattr(
            content,
            "hero_images",
            [],
        )

        if not hero_images:
            logger.info(
                "Hero image validation skipped | no hero images."
            )
            return [], [], 100

        if not self.gemini_client:
            logger.warning(
                "Hero image validation skipped | "
                "Gemini client is not configured."
            )
            return [], [], 100

        destination = self._resolve_destination(
            user_prompt
        )

        intended_destination = destination.get(
            "destination",
            "",
        )

        if not intended_destination:
            logger.warning(
                "Hero image validation skipped | "
                "destination could not be resolved."
            )
            return [], [], 100

        logger.info(
            "Hero image validation started | "
            "destination=%s | images=%d",
            intended_destination,
            len(hero_images),
        )

        try:
            result = self._validate_hero_images_with_gemini(
                user_prompt=user_prompt,
                destination=intended_destination,
                hero_images=hero_images,
            )
        except Exception:
            logger.exception(
                "Hero image Gemini validation failed."
            )

            # Do not invent a geographic mismatch when the
            # external vision service itself failed.
            return [], [], 100

        issues = []
        recommendations = []

        valid_count = 0
        mismatch_count = 0
        uncertain_count = 0

        for item in result.results:
            status = item.status.strip().lower()

            if status == "valid":
                valid_count += 1
                continue

            if status == "uncertain":
                uncertain_count += 1

                logger.warning(
                    "Hero image uncertain | index=%d | "
                    "detected_location=%s | reason=%s",
                    item.image_index,
                    item.detected_location,
                    item.reason,
                )

                continue

            mismatch_count += 1

            image_number = item.image_index + 1

            reason = item.reason.strip()

            detected_location = (
                item.detected_location.strip()
            )

            description = (
                f"Hero image {image_number} does not match "
                f"the destination requested by the user: "
                f"'{intended_destination}'."
            )

            if detected_location:
                description += (
                    f" The image appears to represent "
                    f"'{detected_location}'."
                )

            if reason:
                description += f" {reason}"

            issue = Issue(
                severity="High",
                title="Hero Image Context Mismatch",
                description=description,
            )

            recommendation = Recommendation(
                title="Review Hero Image",
                description=(
                    f"Replace hero image {image_number} with an "
                    f"image that represents '{intended_destination}'."
                ),
            )

            issues.append(issue)
            recommendations.append(
                recommendation
            )

        total_images = len(hero_images)

        # Only confirmed mismatches reduce the score.
        # Uncertain images are reported but do not become
        # false mismatches.
        image_score = round(
            (
                (total_images - mismatch_count)
                / total_images
            )
            * 100
        )

        logger.info(
            "Hero image validation completed | "
            "total=%d | valid=%d | mismatch=%d | "
            "uncertain=%d | score=%d",
            total_images,
            valid_count,
            mismatch_count,
            uncertain_count,
            image_score,
        )

        return (
            issues,
            recommendations,
            image_score,
        )

    def _validate_hero_images_with_gemini(
        self,
        user_prompt: str,
        destination: str,
        hero_images,
    ) -> HeroImageValidationLLMResult:
        """Send hero images to Gemini for geographic validation.

        Parameters:
            user_prompt: Original user prompt.
            destination: Destination resolved from the user prompt.
            hero_images: Hero-section image objects.

        Returns:
            Structured Gemini validation result.
        """
        parts = [
            types.Part.from_text(
                text=self._build_hero_image_prompt(
                    user_prompt=user_prompt,
                    destination=destination,
                    image_count=len(hero_images),
                )
            )
        ]

        valid_image_count = 0

        for index, image in enumerate(hero_images):
            image_part = self._image_to_gemini_part(
                image
            )

            if image_part is None:
                logger.warning(
                    "Skipping inaccessible hero image | index=%d | src=%s",
                    index,
                    getattr(image, "src", ""),
                )
                continue

            parts.append(
                types.Part.from_text(
                    text=f"\nIMAGE INDEX: {index}\n"
                )
            )

            parts.append(
                image_part
            )

            valid_image_count += 1

        if valid_image_count == 0:
            logger.warning(
                "No hero images could be sent to Gemini."
            )

            return HeroImageValidationLLMResult(
                results=[]
            )

        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=HeroImageValidationLLMResult,
                temperature=0,
            ),
        )

        if not response.parsed:
            raise ValueError(
                "Gemini returned no structured hero-image result."
            )

        return response.parsed

    @staticmethod
    def _build_hero_image_prompt(
        user_prompt: str,
        destination: str,
        image_count: int,
    ) -> str:
        """Build the Gemini prompt for hero-image validation.

        Parameters:
            user_prompt: Original user prompt.
            destination: Destination resolved from the user prompt.
            image_count: Number of hero images.

        Returns:
            Strict multimodal validation prompt.
        """
        return f"""
You are a geographic image validator inside a webpage
knowledge-validation system.

Your ONLY task is to determine whether each supplied hero image
is geographically compatible with the requested destination.

USER PROMPT:
{user_prompt}

INTENDED DESTINATION:
{destination}

NUMBER OF HERO IMAGES:
{image_count}

IMPORTANT SOURCE-OF-TRUTH RULE:

The USER PROMPT is the ONLY source of truth for the intended
destination.

Do NOT change the intended destination based on:
- the image
- image filename
- image URL
- image alt text
- webpage title
- webpage headings
- webpage body content
- other images

The image is evidence that must be evaluated against the
destination already determined from the user prompt.

For every image return exactly one status:

valid
context_mismatch
uncertain

VALID:
Use only when the image provides reasonable visual evidence
that it represents the requested destination.

CONTEXT_MISMATCH:
Use when the image clearly represents a different identifiable
destination or contains strong geographic evidence inconsistent
with the requested destination.

Examples:
- Requested destination = Cox's Bazar
- Image clearly depicts Bali -> context_mismatch
- Image clearly depicts Saint Martin -> context_mismatch

UNCERTAIN:
Use when the image is geographically generic or the visual
evidence is insufficient to establish the exact destination.

Examples:
- Generic tropical beach
- Generic ocean
- Generic hotel room
- Generic sunset

Do NOT guess.

Do NOT identify a destination merely because the image could
possibly have been taken there.

Do NOT use country-level similarity as proof of destination.
For example, an arbitrary Bangladesh beach is not automatically
Cox's Bazar.

Do NOT use visual similarity alone to claim a destination.

Return one result for every supplied image.

The image_index must be the zero-based IMAGE INDEX supplied
before each image.

Return ONLY the structured output.
"""

    @staticmethod
    def _image_to_gemini_part(
        image,
    ):
        """Convert an extracted image into a Gemini image part.

        Parameters:
            image: Extracted webpage image object containing src.

        Returns:
            Gemini image part or None when the image cannot be loaded.
        """
        src = str(
            getattr(image, "src", "")
            or ""
        ).strip()

        if not src:
            return None

        if src.startswith(
            (
                "data:image/",
            )
        ):
            return KnowledgeValidationEvaluator._data_uri_to_part(
                src
            )

        if src.startswith(
            (
                "http://",
                "https://",
            )
        ):
            return KnowledgeValidationEvaluator._remote_image_to_part(
                src
            )

        logger.warning(
            "Unsupported hero image source | src=%s",
            src,
        )

        return None

    @staticmethod
    def _data_uri_to_part(
        data_uri: str,
    ):
        """Convert a data URI image into a Gemini image part.

        Parameters:
            data_uri: Base64 image data URI.

        Returns:
            Gemini image part.
        """
        try:
            header, encoded = data_uri.split(
                ",",
                1,
            )

            mime_type = header.split(
                ";",
                1,
            )[0].replace(
                "data:",
                "",
            )

            image_bytes = base64.b64decode(
                encoded
            )

            return types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )

        except Exception:
            logger.exception(
                "Failed to decode hero image data URI."
            )
            return None

    @staticmethod
    def _remote_image_to_part(
        url: str,
    ):
        """Download a remote hero image and convert it to Gemini input.

        Parameters:
            url: Public image URL.

        Returns:
            Gemini image part.
        """
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "QualistoKnowledgeValidator/1.0"
                    )
                },
            )

            response.raise_for_status()

            content_type = (
                response.headers.get(
                    "Content-Type",
                    "",
                ).split(
                    ";",
                    1,
                )[0]
                .strip()
                .lower()
            )

            if not content_type.startswith(
                "image/"
            ):
                guessed_type = (
                    mimetypes.guess_type(
                        urlparse(url).path
                    )[0]
                )

                if not guessed_type or not guessed_type.startswith(
                    "image/"
                ):
                    logger.warning(
                        "URL did not return an image | url=%s | "
                        "content_type=%s",
                        url,
                        content_type,
                    )
                    return None

                content_type = guessed_type

            return types.Part.from_bytes(
                data=response.content,
                mime_type=content_type,
            )

        except Exception:
            logger.exception(
                "Failed to download hero image | url=%s",
                url,
            )
            return None






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


        if intended_destination and card_city:
            if (
                intended_destination == card_city
                or card_city == intended_destination
            ):
                return "valid"


            dest_words = intended_destination.split()
            city_words = card_city.split()

            if city_words and dest_words[: len(city_words)] == city_words:
                return "valid"

            if dest_words and city_words[: len(dest_words)] == dest_words:
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
        card_city = str(getattr(card, "city", "")).strip()
        card_location = str(getattr(card, "location", "")).strip()
        card_country = str(getattr(card, "country", "")).strip()
        dest_name = str(destination.get("destination", "")).strip()
        dest_country = str(destination.get("country", "")).strip()

        # Deliberately exclude card.title and card.property_type:
        # marketing copy ("For NYC", "Downtown Getaway", etc.) pollutes
        # search results and must never be used as location evidence.
        if not card_city or not dest_name:
            return ""

        query = (
            f'Is "{card_city}" ({card_location}) part of the city of '
            f'"{dest_name}", {card_country or dest_country}? '
            f"administrative boundaries city limits"
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

Country identity has ALREADY been verified to match between the
property and the intended destination. Do NOT reason about country
identity, country spelling, or country codes. Your ONLY job is to
determine whether the property's CITY/ADMINISTRATIVE LOCATION is
inside the intended destination.

USER PROMPT:
{user_prompt}

INTENDED DESTINATION:
{destination.get("destination", "")}

PROPERTY CITY:
{getattr(card, "city", "")}

PROPERTY LOCATION:
{getattr(card, "location", "")}

TAVILY GEOGRAPHIC EVIDENCE:
{evidence or "No external evidence available."}

DISAMBIGUATION NOTE:

If the intended destination is a city and the PROPERTY CITY field is
written as a common short name or alias for that same city (e.g. the
destination is "New York City" and the property city is written as
"New York," "NYC," or "Manhattan"), treat it as referring to the
SAME CITY, not a state, region, or unrelated place that happens to
share the name. Only treat it as a different jurisdiction if the
PROPERTY LOCATION or evidence clearly places the property somewhere
else (e.g. "Albany, NY" or "Buffalo, NY" would indicate a different
city within the state, not the destination city itself).

DECISION PROCEDURE — follow in this exact order, stop at the first match:

Step 1. Is the property city the SAME name as the intended
destination, OR a common short name/alias for the same city (see
DISAMBIGUATION NOTE above)? -> valid.

Step 2. Is the property city an officially recognized neighborhood,
borough, ward, or district that is LEGALLY/ADMINISTRATIVELY part of
the intended destination's city limits (not just commonly associated
with it)? -> valid.

Step 3. Is the property city an INDEPENDENT municipality, town, or
city with its own separate local government, even if adjacent to,
economically tied to, or in the same metro area as the intended
destination? -> context_mismatch. This is true even if it is in the
same state/region as the intended destination.

Step 4. Evidence is ambiguous, conflicting, or silent on legal/
administrative membership -> context_mismatch.

RULES THAT APPLY WITHIN THE STEPS ABOVE:

- Metropolitan-area membership, geographic proximity, shared airport,
  or common branding/marketing association are NEVER sufficient for
  "valid" on their own — they do not establish legal membership.
- Do not use property title or property_type as evidence.
- "Merely nearby" or "commonly grouped with" is always
  context_mismatch, even if evidence discusses the relationship.
- Do not broaden the intended destination beyond its own city limits.
- Do not narrow a common alias/short name for the destination city
  into a state or region reading just to appear "strict." A short
  name for the destination city is still the destination city.

WORKED EXAMPLES (for calibration only, do not copy verbatim):

Destination "New York City", property city "Jersey City, NJ":
Jersey City is an independent municipality in a different state with
its own government -> context_mismatch. Being in the "NYC metro area"
or marketed as "near NYC" does not change this.

Destination "New York City", property city "Flushing, NY":
Flushing is a neighborhood within the borough of Queens, one of NYC's
five legal boroughs -> valid.

Destination "New York City", property city "New York", property
location "New York, NY, USA":
"New York" here is a common short name for New York City itself, not
a reference to New York State as a whole -> valid.

Do not evaluate: property quality, price, amenities, images, SEO,
HTML, readability, writing style.

Return only structured output.

status must be exactly:
valid
or
context_mismatch

If context_mismatch, give a short, concrete administrative reason
(name the actual separate jurisdiction). Do not restate country facts
in the reason.
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


