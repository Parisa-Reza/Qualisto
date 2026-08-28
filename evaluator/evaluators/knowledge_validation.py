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
    status: str = Field(description="verified, unsupported, or uncertain")
    claim: str = ""
    evidence: str = ""
    location: str = ""
    explanation: str = ""

class DestinationResolutionLLMResult(BaseModel):
    destination: str = ""
    country: str = ""
    country_code: str = ""
    explanation: str = ""

class CountryResolutionLLMResult(BaseModel):
    country: str = ""
    country_code: str = ""
    confidence: str = Field(default="uncertain", description="high, medium, or low")
    explanation: str = ""

class PropertyCardValidationLLMResult(BaseModel):
    status: str = Field(description="valid or context_mismatch")
    reason: str = ""

class HeroImageValidationItem(BaseModel):
    image_index: int = Field(description="Zero-based index of the hero image.")
    status: str = Field(description="valid, context_mismatch, or uncertain")
    detected_location: str = ""
    reason: str = ""

class HeroImageValidationLLMResult(BaseModel):
    results: list[HeroImageValidationItem] = Field(default_factory=list)

class KnowledgeFinding(BaseModel):
    """A single concrete knowledge issue paired with its own recommendation.

    Issue and recommendation live on the same object so the model can't
    emit one without the other (which is what was producing
    recommendations with no matching issue).
    """
    issue: str = Field(description="The concrete knowledge problem found.")
    recommendation: str = Field(description="The specific fix for this exact issue.")

class KnowledgeValidationLLMResult(BaseModel):
    score: int = Field(ge=0, le=100)
    verified_claims: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    uncertain_claims: list[str] = Field(default_factory=list)
    findings: list[KnowledgeFinding] = Field(default_factory=list)

    @property
    def issues(self) -> list[str]:
        return [f.issue for f in self.findings]

    @property
    def recommendations(self) -> list[str]:
        return [f.recommendation for f in self.findings]

# New models for multiple destinations
class Destination(BaseModel):
    destination: str = ""
    country: str = ""
    country_code: str = ""
    explanation: str = ""

class DestinationList(BaseModel):
    destinations: list[Destination] = Field(default_factory=list)

class KnowledgeValidationEvaluator:
    def __init__(self, llm, search_client, gemini_client=None, gemini_model: str = "gemini-3.1-flash-lite", max_workers: int = 4):
        self.llm = llm
        self.search_client = search_client
        self.gemini_client = gemini_client
        self.gemini_model = gemini_model
        self.max_workers = max_workers
        logger.info("KnowledgeValidationEvaluator initialized | llm=%s | search_client=%s | gemini_enabled=%s | gemini_model=%s | max_workers=%d",
                    type(llm).__name__, type(search_client).__name__, bool(gemini_client), gemini_model, max_workers)

    def evaluate(self, content: WebsiteContent, user_prompt: str) -> KnowledgeValidationResult:
        logger.info("Knowledge validation started | user_prompt=%s", user_prompt[:300])
        general_result = self._analyze(content, user_prompt)
        issues, recommendations = [], []
        for finding in general_result.findings:
            if not finding.issue:
                continue
            issues.append(Issue(severity=self._issue_severity(general_result.score), title="Knowledge Validation", description=finding.issue))
            if finding.recommendation:
                recommendations.append(Recommendation(title="Fix Knowledge Issue", description=finding.recommendation))
        image_issues, image_recommendations, image_score = self._validate_hero_images(content=content, user_prompt=user_prompt)
        issues.extend(image_issues)
        recommendations.extend(image_recommendations)
        card_issues, card_recommendations, card_score = self._validate_property_cards(content, user_prompt)
        issues.extend(card_issues)
        recommendations.extend(card_recommendations)
        property_type_issues, property_type_recommendations, property_type_score = (self._validate_property_type_tabs(content))
        issues.extend(property_type_issues)
        recommendations.extend(property_type_recommendations)
        scores = [general_result.score]
        if getattr(content, "property_cards", []):
            scores.append(card_score)
        if self._has_hero_images(content):
            scores.append(image_score)
        if getattr(content,"property_type_tabs",[]):
            scores.append(property_type_score)
        score = min(scores)
        logger.info("Knowledge validation completed | general_score=%d | card_score=%d | image_score=%d | property_type_score=%d |final_score=%d",
                    general_result.score, card_score, image_score,property_type_score, score)
        return KnowledgeValidationResult(score=score, issues=issues, recommendations=recommendations,
                                         verified_claims=general_result.verified_claims,
                                         unsupported_claims=general_result.unsupported_claims,
                                         uncertain_claims=general_result.uncertain_claims)

    #  GENERAL KNOWLEDGE 
    def _analyze(self, content: WebsiteContent, user_prompt: str) -> KnowledgeValidationLLMResult:
        search_evidence = self._collect_search_evidence(content, user_prompt)
        structured_llm = self.llm.with_structured_output(KnowledgeValidationLLMResult)
        result = structured_llm.invoke(self._build_prompt(content=content, user_prompt=user_prompt, search_evidence=search_evidence))
        logger.info("General knowledge validation LLM call successful.")
        return result

    #  MULTIPLE DESTINATION EXTRACTION 
    def _resolve_destinations(self, user_prompt: str) -> list[dict]:
        """
        Extract all geographic destinations from the user prompt.

        Small/local LLMs are unreliable at *segmenting* a list of
        destinations inside a structured-output call - they tend to
        collapse several distinct places into one generic entry (e.g.
        four Bahamas towns collapsing into a single "Bahamas" entry).

        To avoid depending on the LLM for something that is really a
        parsing problem, we first try a purely structural, deterministic
        parse: if the prompt is itself already a delimited list of
        candidate destinations (quoted list, comma-separated list, or
        one-per-line list), we split it ourselves and only use the LLM
        to resolve each candidate's country/country_code.

        This is fully generic - no place names, countries, or specific
        prompt formats are hardcoded. If the prompt doesn't structurally
        look like a list, we fall back to the original free-text LLM
        extraction unchanged.
        """
        candidates = self._extract_destination_candidates(user_prompt)

        if candidates:
            logger.info(
                "Destination extraction used deterministic list parsing | candidates=%d",
                len(candidates),
            )
            return self._resolve_candidate_destinations(candidates)

        return self._resolve_destinations_via_llm(user_prompt)

    @staticmethod
    def _extract_destination_candidates(user_prompt: str) -> list[str]:
        """
        Structurally detect whether the prompt is a delimited list of
        destinations and, if so, return each entry as a separate
        candidate string.

        Detection strategies, tried in order, each purely structural
        (no hardcoded vocabulary):

        1. Quoted entries: "A, B", "C, D", ...
           Matches any string wrapped in double or single quotes.
        2. One-destination-per-line: entries separated by newlines,
           optionally with list markers (-, *, digits, bullets).
        3. Comma-separated single-line list, but only when each
           resulting segment itself looks like "Place, Country"
           (i.e. contains exactly one internal comma), so that a
           single free-text sentence with incidental commas is not
           misread as a destination list.

        Returns [] (meaning "not a list") if fewer than 2 distinct
        candidates are found by any strategy, so the caller safely
        falls back to LLM-based free-text extraction for ordinary
        prose prompts.
        """
        if not user_prompt or not user_prompt.strip():
            return []

        # Strategy 1: quoted entries.
        quoted = re.findall(r'["\']([^"\']+)["\']', user_prompt)
        quoted = [q.strip() for q in quoted if q.strip()]
        if len(quoted) >= 2:
            return quoted

        # Strategy 2: one entry per line.
        lines = [line.strip() for line in user_prompt.splitlines()]
        lines = [re.sub(r"^[\-\*\u2022\d\.\)]+\s*", "", line).strip() for line in lines]
        lines = [line for line in lines if line]
        if len(lines) >= 2:
            return lines

        # Strategy 3: comma-separated list where every segment looks
        # like "Place, Country" (exactly one internal comma each).
        raw_segments = [seg.strip() for seg in user_prompt.split(",")]
        raw_segments = [seg for seg in raw_segments if seg]
        if len(raw_segments) >= 4 and len(raw_segments) % 2 == 0:
            # Pair consecutive segments back into "Place, Country" entries.
            paired = [
                f"{raw_segments[i]}, {raw_segments[i + 1]}"
                for i in range(0, len(raw_segments) - 1, 2)
            ]
            if len(paired) >= 2:
                return paired

        return []

    @staticmethod
    def _split_place_country(candidate: str) -> tuple[str, str]:
        """
        Split a "Place, Country" style candidate on its LAST comma,
        since place names can themselves legitimately contain commas
        (e.g. "Governor's Harbour, Eleuthera, Bahamas"). If there is no
        comma, the whole candidate is treated as the place name with no
        country hint.
        """
        candidate = candidate.strip()
        if "," in candidate:
            place, _, country = candidate.rpartition(",")
            return place.strip(), country.strip()
        return candidate, ""

    def _resolve_candidate_destinations(self, candidates: list[str]) -> list[dict]:
        """Resolve a deterministically-split list of candidate destination strings."""
        result = []
        seen = set()
        for candidate in candidates:
            place_raw, country_hint_raw = self._split_place_country(candidate)
            dest_name = self._normalize_text(place_raw)
            if not dest_name:
                continue
            country = self._normalize_text(country_hint_raw)
            country_code = ""
            if not country or not country_code:
                resolved = self._resolve_country_identity(
                    country=country, country_code=country_code, context=candidate
                )
                if resolved:
                    country = resolved["country"]
                    country_code = resolved["country_code"]
            key = (dest_name, country_code)
            if key in seen:
                continue
            seen.add(key)
            result.append({"destination": dest_name, "country": country, "country_code": country_code})
        logger.info("Resolved %d destinations", len(result))
        return result

    def _resolve_destinations_via_llm(self, user_prompt: str) -> list[dict]:
        """Original free-text LLM-based multi-destination extraction."""
        structured_llm = self.llm.with_structured_output(DestinationList)
        try:
            extracted = structured_llm.invoke(self._build_destinations_prompt(user_prompt))
        except Exception:
            logger.exception("Destination extraction failed.")
            return []
        result = []
        for dest in extracted.destinations:
            dest_name = self._normalize_text(dest.destination)
            country = self._normalize_text(dest.country)
            country_code = self._normalize_country_code(dest.country_code)
            if not dest_name:
                continue
            # Try to resolve country if missing
            if not country or not country_code:
                resolved = self._resolve_country_identity(country=country, country_code=country_code, context=dest.destination)
                if resolved:
                    country = resolved["country"]
                    country_code = resolved["country_code"]
            result.append({"destination": dest_name, "country": country, "country_code": country_code})
        logger.info("Resolved %d destinations", len(result))
        return result

    @staticmethod
    def _build_destinations_prompt(user_prompt: str) -> str:
        return f"""
You are a geographic destination extraction system.
USER PROMPT:
{user_prompt}
Extract ALL geographic destinations that the user explicitly wants the webpage to be about.
Return a list of destinations. For each, provide destination name, country, country code (ISO 3166-1 alpha-2), and explanation.
Rules:
- The USER PROMPT is the only authority for destination intent.
- Ignore webpage content, titles, etc.
- Extract every distinct geographic location mentioned as a primary subject.
- If the user lists multiple places, include each one as its own separate destination. Do NOT merge multiple distinct places into a single broader entry (e.g. do not collapse "Paris, France" and "Lyon, France" into one "France" entry).
- If the prompt contains N distinct place names, return N destinations, not fewer.
- If the prompt is ambiguous or contains only a country, that country is the destination.
- Country code must be ISO 3166-1 alpha-2. Do not use state/province/airport/postal codes.
- If a destination cannot be confidently resolved to a country, leave country and country_code empty.
Return only structured output.
"""

    #  DESTINATION RESOLUTION (single, for backward compatibility) 
    def _resolve_destination(self, user_prompt: str) -> dict:
        """Legacy single-destination resolver; returns first destination or empty."""
        dests = self._resolve_destinations(user_prompt)
        return dests[0] if dests else {}

    def _resolve_country_identity(self, country: str, country_code: str, context: str = "") -> dict:
        country = self._normalize_text(country)
        country_code = self._normalize_country_code(country_code)
        if not country and not country_code:
            return {}
        if country_code:
            return {"country": country, "country_code": country_code}
        structured_llm = self.llm.with_structured_output(CountryResolutionLLMResult)
        evidence = ""
        if self.search_client and (country or country_code):
            query = " ".join(str(v).strip() for v in [country, country_code, context, "country ISO 3166 alpha 2"] if v)
            try:
                results = self.search_client.search(query=query[:400], max_results=5)
                evidence = self._format_search_results(results)
            except Exception:
                logger.exception("Country identity Tavily search failed | country=%s | country_code=%s", country, country_code)
        try:
            result = structured_llm.invoke(self._build_country_resolution_prompt(country=country, country_code=country_code,
                                                                                 context=context, evidence=evidence))
        except Exception:
            logger.exception("Country identity resolution failed | country=%s | country_code=%s", country, country_code)
            return {}
        resolved_country = self._normalize_text(result.country)
        resolved_code = self._normalize_country_code(result.country_code)
        confidence = str(result.confidence).strip().lower()
        if not resolved_country or not resolved_code or confidence == "low":
            logger.warning("Country identity unresolved | input_country=%s | input_code=%s | resolved_country=%s | resolved_code=%s | confidence=%s",
                           country, country_code, resolved_country, resolved_code, confidence)
            return {}
        logger.info("Country identity resolved | input_country=%s | input_code=%s | canonical_country=%s | canonical_code=%s",
                    country, country_code, resolved_country, resolved_code)
        return {"country": resolved_country, "country_code": resolved_code}

    @staticmethod
    def _build_country_resolution_prompt(country: str, country_code: str, context: str, evidence: str) -> str:
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
1. Resolve abbreviations, short names, alternative names, conventional names dynamically.
2. Examples are illustrative only: "USA" may refer to "United States".
3. Do not rely on those examples as a hardcoded mapping.
4. The country_code must be ISO 3166-1 alpha-2.
5. Do not return state/province/city/airport/postal/regional/marketing codes.
6. country and country_code must identify the same sovereign country.
7. Use external evidence when available.
8. If the representation cannot be resolved confidently, return empty country and country_code.
9. Confidence must be high, medium, or low.
Return only structured output.
"""

    def _resolve_destination_with_search(self, destination: str) -> str:
        if not self.search_client or not destination:
            return ""
        query = f"{destination} country official geographic location"
        try:
            results = self.search_client.search(query=query, max_results=5)
        except Exception:
            logger.exception("Destination Tavily search failed.")
            return ""
        return self._format_search_results(results)

    @staticmethod
    def _build_destination_prompt(user_prompt: str) -> str:
        return f"""
You are a geographic destination extraction system.
USER PROMPT:
{user_prompt}
Extract the PRIMARY geographic destination that the requested webpage is supposed to be about.
Return: destination, country, country_code, explanation.
Rules:
1. The USER PROMPT is the only authority for destination intent.
2. Ignore webpage titles, headings, property cards, hotel names, property locations, and webpage content.
3. Extract the destination the user actually requested.
4. The destination may be a city, municipality, country, state, region, island, or other geographic area.
5. Determine the sovereign country containing the destination.
6. country_code must be the ISO 3166-1 alpha-2 code of that country.
7. Do not return state, province, city, airport, postal, regional, or marketing codes.
8. If the country is not explicitly stated but the destination is geographically unambiguous, the country may be resolved.
9. If the country cannot be resolved confidently, return empty country and country_code.
10. Do not derive a country code from letters contained in the destination name.
Return only structured output.
"""

    @staticmethod
    def _build_destination_resolution_prompt(user_prompt: str, destination: str, evidence: str) -> str:
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
- Do not confuse a city with a state/airport/metropolitan area.
- Do not use state/province/airport/postal codes.
- Do not guess.
- Use external evidence.
- If the country cannot be established confidently, leave country and country_code empty.
Return only structured output.
"""

    #  HERO IMAGE VALIDATION 
    def _has_hero_images(self, content: WebsiteContent) -> bool:
        return bool(getattr(content, "hero_images", None))

    def _validate_hero_images(self, content: WebsiteContent, user_prompt: str):
        hero_images = getattr(content, "hero_images", [])
        if not hero_images:
            logger.info("Hero image validation skipped | no hero images.")
            return [], [], 100
        if not self.gemini_client:
            logger.warning("Hero image validation skipped | Gemini client is not configured.")
            return [], [], 100
        destination = self._resolve_destination(user_prompt)
        intended_destination = destination.get("destination", "")
        if not intended_destination:
            logger.warning("Hero image validation skipped | destination could not be resolved.")
            return [], [], 100
        logger.info("Hero image validation started | destination=%s | images=%d", intended_destination, len(hero_images))
        try:
            result = self._validate_hero_images_with_gemini(user_prompt=user_prompt, destination=intended_destination,
                                                            hero_images=hero_images)
        except Exception:
            logger.exception("Hero image Gemini validation failed.")
            return [], [], 100
        issues, recommendations = [], []
        valid_count = mismatch_count = uncertain_count = 0
        for item in result.results:
            status = item.status.strip().lower()
            if status == "valid":
                valid_count += 1
            elif status == "uncertain":
                uncertain_count += 1
                logger.warning("Hero image uncertain | index=%d | detected_location=%s | reason=%s",
                               item.image_index, item.detected_location, item.reason)
            else:
                mismatch_count += 1
                image_number = item.image_index + 1
                description = f"Hero image {image_number} does not match the destination '{intended_destination}'."
                if item.detected_location:
                    description += f" The image appears to represent '{item.detected_location}'."
                if item.reason:
                    description += f" {item.reason}"
                issues.append(Issue(severity="High", title="Hero Image Context Mismatch", description=description))
                recommendations.append(Recommendation(title="Review Hero Image",
                                                      description=f"Replace hero image {image_number} with an image that represents '{intended_destination}'."))
        total_images = len(hero_images)
        image_score = round(((total_images - mismatch_count) / total_images) * 100)
        logger.info("Hero image validation completed | total=%d | valid=%d | mismatch=%d | uncertain=%d | score=%d",
                    total_images, valid_count, mismatch_count, uncertain_count, image_score)
        return issues, recommendations, image_score

    def _validate_hero_images_with_gemini(self, user_prompt: str, destination: str, hero_images):
        parts = [types.Part.from_text(text=self._build_hero_image_prompt(user_prompt=user_prompt,
                                                                         destination=destination,
                                                                         image_count=len(hero_images)))]
        valid_image_count = 0
        for index, image in enumerate(hero_images):
            image_part = self._image_to_gemini_part(image)
            if image_part is None:
                logger.warning("Skipping inaccessible hero image | index=%d | src=%s", index, getattr(image, "src", ""))
                continue
            parts.append(types.Part.from_text(text=f"\nIMAGE INDEX: {index}\n"))
            parts.append(image_part)
            valid_image_count += 1
        if valid_image_count == 0:
            logger.warning("No hero images could be sent to Gemini.")
            return HeroImageValidationLLMResult(results=[])
        response = self.gemini_client.models.generate_content(
            model=self.gemini_model,
            contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               response_schema=HeroImageValidationLLMResult, temperature=0))
        if not response.parsed:
            raise ValueError("Gemini returned no structured hero-image result.")
        return response.parsed

    @staticmethod
    def _build_hero_image_prompt(user_prompt: str, destination: str, image_count: int) -> str:
        return f"""
You are a geographic image validator.
USER PROMPT:
{user_prompt}
INTENDED DESTINATION:
{destination}
NUMBER OF HERO IMAGES:
{image_count}
IMPORTANT: The USER PROMPT is the ONLY source of truth for the intended destination.
Do NOT change the intended destination based on image filename, URL, alt text, webpage title, or content.
For every image return exactly one status: valid, context_mismatch, or uncertain.
VALID: only when the image provides reasonable visual evidence that it represents the requested destination.
CONTEXT_MISMATCH: when the image clearly represents a different identifiable destination or contains strong geographic evidence inconsistent with the requested destination.
UNCERTAIN: when the image is geographically generic or insufficient evidence.
Do NOT guess. Do NOT identify a destination merely because the image could possibly have been taken there.
Return one result for every supplied image. The image_index must be the zero-based IMAGE INDEX supplied before each image.
Return ONLY structured output.
"""

    @staticmethod
    def _image_to_gemini_part(image):
        src = str(getattr(image, "src", "") or "").strip()
        if not src:
            return None
        if src.startswith(("data:image/",)):
            return KnowledgeValidationEvaluator._data_uri_to_part(src)
        if src.startswith(("http://", "https://")):
            return KnowledgeValidationEvaluator._remote_image_to_part(src)
        logger.warning("Unsupported hero image source | src=%s", src)
        return None

    @staticmethod
    def _data_uri_to_part(data_uri: str):
        try:
            header, encoded = data_uri.split(",", 1)
            mime_type = header.split(";", 1)[0].replace("data:", "")
            image_bytes = base64.b64decode(encoded)
            return types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        except Exception:
            logger.exception("Failed to decode hero image data URI.")
            return None

    @staticmethod
    def _remote_image_to_part(url: str):
        try:
            response = requests.get(url, timeout=15, headers={"User-Agent": "QualistoKnowledgeValidator/1.0"})
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/"):
                guessed_type = mimetypes.guess_type(urlparse(url).path)[0]
                if not guessed_type or not guessed_type.startswith("image/"):
                    logger.warning("URL did not return an image | url=%s | content_type=%s", url, content_type)
                    return None
                content_type = guessed_type
            return types.Part.from_bytes(data=response.content, mime_type=content_type)
        except Exception:
            logger.exception("Failed to download hero image | url=%s", url)
            return None

    #  PROPERTY CARD VALIDATION (UPDATED FOR MULTIPLE DESTINATIONS) 
    def _validate_property_cards(self, content: WebsiteContent, user_prompt: str):
        cards = getattr(content, "property_cards", [])
        if not cards:
            return [], [], 100
        destinations = self._resolve_destinations(user_prompt)
        if not destinations:
            logger.warning("Property card validation skipped | no destinations resolved.")
            return [], [], 100
        logger.info("Resolved %d destinations for property cards", len(destinations))
        valid_cards, invalid_cards, ambiguous_cards = [], [], []
        for index, card in enumerate(cards):
            decision = self._deterministic_card_match(card, destinations)
            logger.info("Property card pre-validation | index=%d | title=%s | city=%s | country=%s | country_code=%s | decision=%s",
                        index, getattr(card, "title", ""), getattr(card, "city", ""), getattr(card, "country", ""),
                        getattr(card, "country_code", ""), decision)
            if decision == "valid":
                valid_cards.append((index, card))
            elif decision == "context_mismatch":
                invalid_cards.append((index, card))
            else:
                ambiguous_cards.append((index, card))
        logger.info("Property card pre-validation completed | valid=%d | invalid=%d | ambiguous=%d",
                    len(valid_cards), len(invalid_cards), len(ambiguous_cards))
        issues, recommendations = [], []
        for _, card in invalid_cards:
            issue, rec = self._build_property_card_issue(card, "The property's country does not match any of the requested destinations.")
            issues.append(issue)
            recommendations.append(rec)
        if ambiguous_cards:
            results = self._verify_ambiguous_cards_parallel(content, user_prompt, destinations, ambiguous_cards)
            for index, issue, rec in results:
                if issue:
                    issues.append(issue)
                if rec:
                    recommendations.append(rec)
                if not issue:
                    valid_cards.append((index, cards[index]))
        total_cards = len(cards)
        valid_count = len(valid_cards)
        card_score = round((valid_count / total_cards) * 100)
        logger.info("Property card scoring | total=%d | valid=%d | invalid=%d | score=%d",
                    total_cards, valid_count, total_cards - valid_count, card_score)
        return issues, recommendations, card_score

    def _deterministic_card_match(self, card, destinations: list[dict]) -> str:
        """Returns 'valid', 'context_mismatch', or 'ambiguous' based on list of destinations."""
        if not destinations:
            return "ambiguous"
        # Gather results for each destination
        statuses = []
        for dest in destinations:
            statuses.append(self._match_single_destination(card, dest))
        if any(s == "valid" for s in statuses):
            return "valid"
        if all(s == "context_mismatch" for s in statuses):
            return "context_mismatch"
        return "ambiguous"

    def _match_single_destination(self, card, dest: dict) -> str:
        """Deterministic match against one destination."""
        intended_country_code = self._normalize_country_code(dest.get("country_code", ""))
        intended_destination = self._normalize_text(dest.get("destination", ""))
        card_country_code = self._normalize_country_code(getattr(card, "country_code", ""))
        card_country = self._normalize_text(getattr(card, "country", ""))
        card_city = self._normalize_text(getattr(card, "city", ""))
        card_location = self._normalize_text(getattr(card, "location", ""))
        # Compare country codes only if both are actual ISO codes
        if intended_country_code and card_country_code and intended_country_code != card_country_code:
            return "context_mismatch"
        # Check city name equality or containment
        if intended_destination and card_city:
            if intended_destination == card_city or card_city == intended_destination:
                return "valid"
            # Check if one is a substring of the other (e.g., "New York" vs "New York City")
            if intended_destination in card_city or card_city in intended_destination:
                return "valid"
            # Check word prefix
            dest_words = intended_destination.split()
            city_words = card_city.split()
            if city_words and dest_words[:len(city_words)] == city_words:
                return "valid"
            if dest_words and city_words[:len(dest_words)] == dest_words:
                return "valid"
        if intended_destination and card_location and intended_destination in card_location:
            return "valid"
        # If no mismatch and no match, ambiguous
        return "ambiguous"

    def _verify_ambiguous_cards_parallel(self, content: WebsiteContent, user_prompt: str, destinations: list[dict],
                                         cards: list[tuple[int, object]]):
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {executor.submit(self._verify_ambiguous_card, content, user_prompt, destinations, index, card): index
                          for index, card in cards}
            for future in as_completed(future_map):
                index = future_map[future]
                try:
                    issue, rec = future.result()
                except Exception:
                    logger.exception("Unexpected property-card validation failure | index=%d", index)
                    # find card
                    card_obj = next(c for i, c in cards if i == index)
                    issue, rec = self._build_property_card_issue(card_obj, "The geographic relationship could not be verified.")
                results.append((index, issue, rec))
        return results

    def _verify_ambiguous_card(self, content: WebsiteContent, user_prompt: str, destinations: list[dict],
                               index: int, card):
        """Verify ambiguous card against all destinations."""
        # Resolve card country
        card_country = self._normalize_text(getattr(card, "country", ""))
        card_country_code = self._normalize_country_code(getattr(card, "country_code", ""))
        card_country_identity = self._resolve_country_identity(country=card_country, country_code=card_country_code,
                                                               context=f"{getattr(card, 'city', '')}, {getattr(card, 'location', '')}")
        if card_country_identity:
            card_resolved_country = card_country_identity["country"]
            card_resolved_code = card_country_identity["country_code"]
            # Check if card's resolved country code matches any destination's country code
            dest_codes = {self._normalize_country_code(d.get("country_code", "")) for d in destinations}
            if card_resolved_code and card_resolved_code not in dest_codes:
                return self._build_property_card_issue(card, "The property's country does not match any of the requested destinations.")
        # Build evidence with search
        evidence = self._collect_single_card_evidence(content, index, card, destinations)
        # LLM validation
        structured_llm = self.llm.with_structured_output(PropertyCardValidationLLMResult)
        prompt = self._build_property_card_prompt(user_prompt=user_prompt, destinations=destinations,
                                                  card=card, evidence=evidence)
        try:
            result = structured_llm.invoke(prompt)
        except Exception:
            logger.exception("Property card LLM validation failed | index=%d", index)
            return self._build_property_card_issue(card, "The geographic relationship could not be verified.")
        status = str(result.status).strip().lower()
        logger.info("Property card LLM validation | index=%d | status=%s | reason=%s", index, status, result.reason)
        if status == "valid":
            return None, None
        return self._build_property_card_issue(card, result.reason or "The property's geographic relationship to any requested destination could not be established.")

    def _collect_single_card_evidence(self, content: WebsiteContent, index: int, card, destinations: list[dict]) -> str:
        if not self.search_client:
            return ""
        query = self._build_card_search_query(card, destinations)
        if not query:
            return ""
        logger.info("Tavily property-card search | index=%d | query=%s", index, query)
        try:
            results = self.search_client.search(query=query, max_results=5)
        except Exception:
            logger.exception("Property-card Tavily search failed | index=%d", index)
            return ""
        return self._format_search_results(results)

    @staticmethod
    def _build_card_search_query(card, destinations: list[dict]) -> str:
        card_city = str(getattr(card, "city", "")).strip()
        card_location = str(getattr(card, "location", "")).strip()
        if not card_city:
            return ""
        dest_names = [str(d.get("destination", "")).strip() for d in destinations if d.get("destination")]
        dest_countries = [str(d.get("country", "")).strip() for d in destinations if d.get("country")]
        if not dest_names:
            return ""
        # Build a query that asks if the card city is part of any of the listed destinations
        dest_list = ", ".join(dest_names)
        query = f'Is "{card_city}" ({card_location}) part of any of these destinations: {dest_list}? administrative boundaries city limits'
        return query[:500]

    @staticmethod
    def _build_property_card_prompt(user_prompt: str, destinations: list[dict], card, evidence: str) -> str:
        dest_list = "\n".join([f"- {d.get('destination', '')} ({d.get('country', '')})" for d in destinations])
        return f"""
You are a STRICT geographic property-card validator.
Country identity has ALREADY been verified to match between the property and at least one intended destination. Do NOT reason about country identity, country spelling, or country codes. Your ONLY job is to determine whether the property's CITY/ADMINISTRATIVE LOCATION is inside ANY of the intended destinations.

USER PROMPT:
{user_prompt}

INTENDED DESTINATIONS:
{dest_list}

PROPERTY CITY:
{getattr(card, "city", "")}

PROPERTY LOCATION:
{getattr(card, "location", "")}

TAVILY GEOGRAPHIC EVIDENCE:
{evidence or "No external evidence available."}

DISAMBIGUATION NOTE:
If a destination is a city and the property city is written as a common short name or alias for that same city (e.g., "New York City" vs "New York"), treat as SAME CITY. Only treat as different jurisdiction if location/evidence clearly places it elsewhere.

DECISION PROCEDURE (stop at first match):
1. Is the property city the SAME name as any intended destination, or a common short name/alias for one of them? -> valid.
2. Is the property city an officially recognized neighborhood, borough, ward, or district that is LEGALLY/ADMINISTRATIVELY part of any intended destination's city limits? -> valid.
3. Is the property city an INDEPENDENT municipality, town, or city with its own separate local government, even if adjacent to or in the same metro area as any destination? -> context_mismatch.
4. Evidence is ambiguous, conflicting, or silent on legal/administrative membership -> context_mismatch.

RULES:
- Metropolitan-area membership, geographic proximity, shared airport, or common branding are NEVER sufficient for "valid".
- Do not use property title or property_type as evidence.
- "Merely nearby" is always context_mismatch.
- Do not broaden a destination beyond its own city limits.
- A short name for a destination city is still the destination city.

Do not evaluate property quality, price, amenities, images, SEO, HTML, readability, or writing style.
Return only structured output.
status must be exactly: valid or context_mismatch.
If context_mismatch, give a short, concrete administrative reason (name the actual separate jurisdiction).
"""

    #  ISSUE CREATION 
    @staticmethod
    def _build_property_card_issue(card, reason: str):
        title = getattr(card, "title", "Unknown property")
        location = getattr(card, "location", "")
        description = f"The property card '{title}'"
        if location:
            description += f" is associated with {location}."
        if reason:
            description += f" {reason}"
        issue = Issue(severity="High", title="Property Card Context Mismatch", description=description)
        recommendation = Recommendation(title="Review Property Card",
                                        description=f"Review the '{title}' property card and remove or replace it if it does not belong to any destination specified by the user. Detected location: '{location}'.")
        return issue, recommendation

    #  SEARCH HELPERS 
    def _collect_search_evidence(self, content: WebsiteContent, user_prompt: str) -> str:
        if not self.search_client:
            return ""
        query = self._build_search_query(content, user_prompt)
        if not query:
            return ""
        try:
            results = self.search_client.search(query=query, max_results=5)
        except Exception:
            logger.exception("General Tavily search failed.")
            return ""
        return self._format_search_results(results)

    @staticmethod
    def _build_search_query(content: WebsiteContent, user_prompt: str) -> str:
        return " ".join(part for part in [user_prompt, content.title] if part)[:400]

    @staticmethod
    def _format_search_results(results) -> str:
        if not results:
            return ""
        evidence = []
        for index, result in enumerate(results, start=1):
            evidence.append(f"Result {index}\nTitle: {result.get('title', '')}\nURL: {result.get('url', '')}\nSnippet: {result.get('content', '')}\n")
        return "\n".join(evidence)

    #  GENERAL KNOWLEDGE PROMPT 
    @staticmethod
    def _build_prompt(content: WebsiteContent, user_prompt: str, search_evidence: str = "") -> str:
        headings = [h for heading_list in (content.headings.h1, content.headings.h2, content.headings.h3, content.headings.h4) for h in heading_list]
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
1. Whether the content matches the destination and subject in the user prompt.
2. Incorrect factual claims.
3. Unsupported factual claims.
4. Contradictory claims.
5. Incorrect destination, attraction, travel, hotel, or property information.
6. Content belonging to another destination.
The USER PROMPT is authoritative for destination intent.
Do not treat webpage headings or title as authoritative for destination identity.
Do not evaluate SEO, HTML, keyword density, readability, writing style, AI-generated style, or property-card images.
If evidence is insufficient, classify the claim as uncertain.
Scoring: 100=accurate and strongly aligned; 80-99=minor issues; 60-79=noticeable issues; 40-59=significant issues; 0-39=major inaccuracies or wrong destination.
Return findings as issue/recommendation pairs. Every finding MUST include BOTH a concrete issue AND a recommendation that directly fixes that specific issue. Never return a recommendation without a matching issue, or an issue without a matching recommendation. Do not invent hypothetical or stylistic recommendations unrelated to a concrete issue you found.
Return only concrete findings.
"""

    @staticmethod
    def _normalize_property_type(value: str) -> str:
        return " ".join(
            str(value or "").strip().lower().split()
        )


    def _validate_property_type_tabs(
        self,
        content: WebsiteContent,
    ) -> tuple[list[Issue], list[Recommendation], int]:

        issues = []
        recommendations = []

        tabs = getattr(
            content,
            "property_type_tabs",
            [],
        )

        if not tabs:
            logger.info(
                "Property-type validation skipped | no tabs found."
            )
            return [], [], 100

        total = 0
        valid = 0

        for tab in tabs:

            expected = self._normalize_property_type(
                tab.tab_name
            )

            for actual in tab.property_types:

                total += 1

                actual_normalized = (
                    self._normalize_property_type(
                        actual
                    )
                )

                if actual_normalized == expected:
                    valid += 1
                    continue

                issues.append(
                    Issue(
                        severity="High",
                        title="Property Type Tab Mismatch",
                        description=(
                            f"The '{tab.tab_name}' tab contains "
                            f"a '{actual}' property."
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Property Type Tab",
                        description=(
                            f"The '{tab.tab_name}' tab should contain "
                            f"only '{tab.tab_name}' properties."
                        ),
                    )
                )

        if total == 0:
            return issues, recommendations, 100

        score = round(
            valid / total * 100
        )

        logger.info(
            "Property-type validation completed | "
            "total=%d | valid=%d | score=%d",
            total,
            valid,
            score,
        )

        return issues, recommendations, score

    #  HELPERS 
    @staticmethod
    def _normalize_text(value: str) -> str:
        value = str(value or "").lower()
        value = re.sub(r"[^a-z0-9\s]", " ", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    @staticmethod
    def _normalize_country_code(value: str) -> str:
        value = str(value or "").strip().upper()
        return value if re.fullmatch(r"[A-Z]{2}", value) else ""

    @staticmethod
    def _issue_severity(score: int) -> str:
        if score < 40:
            return "High"
        if score < 70:
            return "Medium"
        return "Low"