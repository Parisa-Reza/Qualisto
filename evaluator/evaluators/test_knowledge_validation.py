"""
Tests for the KnowledgeValidationEvaluator.

Coverage:
    - General knowledge validation
    - Destination resolution (multi-destination)
    - Country identity resolution
    - Hero image validation using Gemini
    - Property-card deterministic validation
    - Property-card LLM validation
    - Final knowledge-validation scoring
    - Failure/fallback behavior

The tests mock all external services:
    - Ollama/LLM
    - Tavily
    - Gemini
    - HTTP image downloads

No real API calls are made.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock


import pytest
from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.knowledge_validation import (
    Destination,
    DestinationList,
    HeroImageValidationItem,
    HeroImageValidationLLMResult,
    KnowledgeFinding,
    KnowledgeValidationEvaluator,
    KnowledgeValidationLLMResult,
    PropertyCardValidationLLMResult,
)

# TEST HELPERS

@pytest.fixture
def evaluator():
    """Create a KnowledgeValidationEvaluator with mocked dependencies."""
    llm = Mock()
    search_client = Mock()

    return KnowledgeValidationEvaluator(
        llm=llm,
        search_client=search_client,
        gemini_client=None,
        gemini_model="gemini-3.1-flash-lite",
    )

@pytest.fixture
def content():
    """Create minimal WebsiteContent for property-card validation tests."""
    return WebsiteContent(
        url="https://example.com",
        title="New York City Hotels",
        meta_description="Hotels in New York City",
        headings=Mock(
            h1=["New York City Hotels"],
            h2=[],
            h3=[],
            h4=[],
            h5=[],
            h6=[],
        ),
        paragraphs=["Hotels in New York City."],
        links=[],
        images=[],
        plain_text="Hotels in New York City.",
        property_cards=[],
        hero_images=[],
        soup=Mock(),
    )


@pytest.fixture
def user_prompt():
    """Original user prompt defining the intended destination."""
    return "Create a travel webpage about New York City."


@pytest.fixture
def destination():
    """A single resolved destination used by property-card validation."""
    return {
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }


@pytest.fixture
def card():
    """Create an ambiguous property card for validation."""
    return Mock(
        title="Example Hotel",
        city="Jersey City",
        location="Jersey City, NJ, USA",
        country="United States",
        country_code="US",
    )

def make_content(
    *,
    title="New York City Travel Guide",
    plain_text="New York City is one of the most visited cities in the United States.",
    hero_images=None,
    property_cards=None,
):
    """
    Create a lightweight WebsiteContent-like object.

    We deliberately use SimpleNamespace here because the evaluator only
    requires the attributes relevant to the test. This keeps the tests
    independent from unrelated extractor implementation details.
    """

    headings = SimpleNamespace(
        h1=["New York City Travel Guide"],
        h2=["Things to Do"],
        h3=[],
        h4=[],
    )

    return SimpleNamespace(
        url="https://example.com",
        title=title,
        meta_description="New York City travel information.",
        headings=headings,
        paragraphs=[],
        links=[],
        images=[],
        plain_text=plain_text,
        hero_images=hero_images or [],
        property_cards=property_cards or [],
    )


def make_hero_image(src):
    """Create a lightweight hero-image object."""

    return SimpleNamespace(
        src=src,
        alt="",
    )


def make_property_card(
    *,
    title="Hotel New York",
    city="New York",
    location="New York, NY, USA",
    country="United States",
    country_code="US",
):
    """Create a lightweight property-card object."""

    return SimpleNamespace(
        title=title,
        city=city,
        location=location,
        country=country,
        country_code=country_code,
        property_type="hotel",
    )


def make_general_llm_result(
    *,
    score=100,
    verified_claims=None,
    unsupported_claims=None,
    uncertain_claims=None,
    issues=None,
    recommendations=None,
):
    """
    Create a structured general knowledge result.

    `issues` and `recommendations` are paired positionally into
    `KnowledgeFinding` objects, matching the current schema where each
    finding carries both its issue and its recommendation together.
    """

    issues = issues or []
    recommendations = recommendations or []

    findings = [
        KnowledgeFinding(issue=issue, recommendation=recommendation)
        for issue, recommendation in zip(issues, recommendations)
    ]

    return KnowledgeValidationLLMResult(
        score=score,
        verified_claims=verified_claims or [],
        unsupported_claims=unsupported_claims or [],
        uncertain_claims=uncertain_claims or [],
        findings=findings,
    )


def make_evaluator(
    *,
    llm=None,
    search_client=None,
    gemini_client=None,
    gemini_model="gemini-3.1-flash-lite",
):
    """
    Create a KnowledgeValidationEvaluator with mocked dependencies.
    """

    return KnowledgeValidationEvaluator(
        llm=llm or MagicMock(),
        search_client=search_client or MagicMock(),
        gemini_client=gemini_client,
        gemini_model=gemini_model,
        max_workers=2,
    )


# GENERAL KNOWLEDGE VALIDATION

def test_build_search_query_uses_user_prompt_and_page_title():
    """
    The general knowledge search query should be based on:
        - user prompt
        - webpage title

    This verifies the current search-query design.
    """

    content = make_content(
        title="New York City Travel Guide"
    )

    query = KnowledgeValidationEvaluator._build_search_query(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    assert "Create a travel page about New York City" in query
    assert "New York City Travel Guide" in query


def test_build_search_query_is_limited_to_400_characters():
    """Search queries must not exceed the evaluator's 400-character limit."""

    content = make_content(
        title="A" * 200
    )

    query = KnowledgeValidationEvaluator._build_search_query(
        content=content,
        user_prompt="B" * 400,
    )

    assert len(query) <= 400


def test_collect_search_evidence_calls_tavily():
    """
    Tavily should be called for general knowledge evidence.
    """

    search_client = MagicMock()

    search_client.search.return_value = [
        {
            "title": "Official NYC Tourism",
            "url": "https://example.com/nyc",
            "content": "New York City is located in the United States.",
        }
    ]

    evaluator = make_evaluator(
        search_client=search_client
    )

    content = make_content()

    evidence = evaluator._collect_search_evidence(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    search_client.search.assert_called_once()

    assert "Official NYC Tourism" in evidence
    assert "https://example.com/nyc" in evidence
    assert "New York City is located" in evidence


def test_collect_search_evidence_returns_empty_when_tavily_fails():
    """
    Tavily failure must not crash knowledge validation.
    """

    search_client = MagicMock()

    search_client.search.side_effect = RuntimeError(
        "Tavily unavailable"
    )

    evaluator = make_evaluator(
        search_client=search_client
    )

    content = make_content()

    evidence = evaluator._collect_search_evidence(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    assert evidence == ""


def test_analyze_returns_structured_llm_result():
    """
    General knowledge validation must use the configured LLM structured
    output schema.
    """

    llm = MagicMock()
    structured_llm = MagicMock()

    expected_result = make_general_llm_result(
        score=95,
        verified_claims=[
            "New York City is in the United States."
        ],
    )

    structured_llm.invoke.return_value = expected_result

    llm.with_structured_output.return_value = structured_llm

    evaluator = make_evaluator(
        llm=llm,
        search_client=MagicMock(),
    )

    content = make_content()

    result = evaluator._analyze(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    llm.with_structured_output.assert_called_once_with(
        KnowledgeValidationLLMResult
    )

    structured_llm.invoke.assert_called_once()

    assert result.score == 95
    assert (
        "New York City is in the United States."
        in result.verified_claims
    )


def test_general_knowledge_score_and_issues_are_returned():
    """
    The evaluator should preserve the structured general knowledge
    score and convert each (issue, recommendation) finding into
    evaluator Issue/Recommendation objects.
    """

    llm = MagicMock()
    structured_llm = MagicMock()

    structured_llm.invoke.return_value = make_general_llm_result(
        score=65,
        verified_claims=["New York City is in the US."],
        unsupported_claims=["Unsupported hotel claim"],
        uncertain_claims=[],
        issues=["One factual claim is incorrect."],
        recommendations=["Correct the factual claim."],
    )

    llm.with_structured_output.return_value = structured_llm

    evaluator = make_evaluator(
        llm=llm,
        search_client=MagicMock(),
        gemini_client=None,
    )

    content = make_content()

    result = evaluator.evaluate(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    assert result.score == 65

    assert len(result.issues) == 1
    assert (
        "One factual claim is incorrect."
        in result.issues[0].description
    )

    assert len(result.recommendations) == 1
    assert (
        "Correct the factual claim."
        in result.recommendations[0].description
    )


# DESTINATION RESOLUTION

def test_resolve_destination_from_user_prompt():
    """
    Destination intent must be extracted from the USER PROMPT using the
    multi-destination schema; `_resolve_destination` returns the first
    resolved destination.
    """

    llm = MagicMock()
    structured_llm = MagicMock()

    structured_llm.invoke.return_value = DestinationList(
        destinations=[
            Destination(
                destination="New York City",
                country="United States",
                country_code="US",
                explanation="Destination resolved from user prompt.",
            )
        ]
    )

    llm.with_structured_output.return_value = structured_llm

    evaluator = make_evaluator(
        llm=llm,
        search_client=MagicMock(),
    )

    result = evaluator._resolve_destination(
        "Create a travel webpage about New York City."
    )

    llm.with_structured_output.assert_called_once_with(
        DestinationList
    )

    assert result == {
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }


def test_resolve_destination_returns_empty_when_destination_extraction_fails():
    """Destination extraction failures should fail safely."""

    llm = MagicMock()

    structured_llm = MagicMock()
    structured_llm.invoke.side_effect = RuntimeError(
        "LLM failure"
    )

    llm.with_structured_output.return_value = structured_llm

    evaluator = make_evaluator(
        llm=llm,
        search_client=MagicMock(),
    )

    result = evaluator._resolve_destination(
        "Create a travel webpage."
    )

    assert result == {}


def test_normalize_country_code_accepts_only_two_letters():
    """Only ISO-style two-letter candidates should survive normalization."""

    assert (
        KnowledgeValidationEvaluator._normalize_country_code("us")
        == "US"
    )

    assert (
        KnowledgeValidationEvaluator._normalize_country_code(" USA ")
        == ""
    )

    assert (
        KnowledgeValidationEvaluator._normalize_country_code("NY")
        == "NY"
    )


def test_normalize_text():
    """Text normalization should lowercase and remove punctuation."""

    result = KnowledgeValidationEvaluator._normalize_text(
        " New York, City! "
    )

    assert result == "new york city"


# HERO IMAGE VALIDATION


def test_has_hero_images():
    """Hero-image presence should be detected correctly."""

    evaluator = make_evaluator()

    content_without_images = make_content(
        hero_images=[]
    )

    content_with_images = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/nyc.jpg"
            )
        ]
    )

    assert evaluator._has_hero_images(
        content_without_images
    ) is False

    assert evaluator._has_hero_images(
        content_with_images
    ) is True


def test_hero_image_validation_skipped_without_gemini_client():
    """
    If hero images exist but Gemini is not configured, validation must
    fail open and return score 100.
    """

    evaluator = make_evaluator(
        gemini_client=None
    )

    content = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/image.jpg"
            )
        ]
    )

    issues, recommendations, score = (
        evaluator._validate_hero_images(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert issues == []
    assert recommendations == []
    assert score == 100


def test_hero_image_validation_valid_image():
    """
    A Gemini-confirmed valid image should not create an issue and
    should preserve a 100 image score.
    """

    gemini_client = MagicMock()

    evaluator = make_evaluator(
        gemini_client=gemini_client
    )

    content = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/nyc.jpg"
            )
        ]
    )

    evaluator._resolve_destination = MagicMock(
        return_value={
            "destination": "new york city",
            "country": "united states",
            "country_code": "US",
        }
    )

    evaluator._validate_hero_images_with_gemini = MagicMock(
        return_value=HeroImageValidationLLMResult(
            results=[
                HeroImageValidationItem(
                    image_index=0,
                    status="valid",
                    detected_location="New York City",
                    reason="The image clearly represents NYC.",
                )
            ]
        )
    )

    issues, recommendations, score = (
        evaluator._validate_hero_images(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert issues == []
    assert recommendations == []
    assert score == 100

    evaluator._validate_hero_images_with_gemini.assert_called_once()


def test_hero_image_validation_context_mismatch():
    """
    A confirmed geographic mismatch must generate:
        - one issue
        - one recommendation
        - reduced image score
    """

    gemini_client = MagicMock()

    evaluator = make_evaluator(
        gemini_client=gemini_client
    )

    content = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/bali.jpg"
            )
        ]
    )

    evaluator._resolve_destination = MagicMock(
        return_value={
            "destination": "new york city",
            "country": "united states",
            "country_code": "US",
        }
    )

    evaluator._validate_hero_images_with_gemini = MagicMock(
        return_value=HeroImageValidationLLMResult(
            results=[
                HeroImageValidationItem(
                    image_index=0,
                    status="context_mismatch",
                    detected_location="Bali",
                    reason=(
                        "The image clearly represents Bali "
                        "rather than New York City."
                    ),
                )
            ]
        )
    )

    issues, recommendations, score = (
        evaluator._validate_hero_images(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert len(issues) == 1
    assert len(recommendations) == 1

    assert issues[0].title == (
        "Hero Image Context Mismatch"
    )

    assert "new york city" in (
        issues[0].description.lower()
    )

    assert "bali" in (
        issues[0].description.lower()
    )

    assert score == 0


def test_hero_image_uncertain_does_not_reduce_score():
    """
    Uncertain images are intentionally not treated as mismatches.

    Example:
        Generic tropical beach

    The current implementation therefore keeps the score at 100.
    """

    gemini_client = MagicMock()

    evaluator = make_evaluator(
        gemini_client=gemini_client
    )

    content = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/generic-beach.jpg"
            )
        ]
    )

    evaluator._resolve_destination = MagicMock(
        return_value={
            "destination": "new york city",
            "country": "united states",
            "country_code": "US",
        }
    )

    evaluator._validate_hero_images_with_gemini = MagicMock(
        return_value=HeroImageValidationLLMResult(
            results=[
                HeroImageValidationItem(
                    image_index=0,
                    status="uncertain",
                    detected_location="",
                    reason="Generic beach image.",
                )
            ]
        )
    )

    issues, recommendations, score = (
        evaluator._validate_hero_images(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert issues == []
    assert recommendations == []
    assert score == 100


def test_hero_image_gemini_failure_fails_open():
    """
    If Gemini itself fails, the evaluator must not invent a mismatch.

    Current expected behavior:
        score = 100
        no issue
        no recommendation
    """

    gemini_client = MagicMock()

    evaluator = make_evaluator(
        gemini_client=gemini_client
    )

    content = make_content(
        hero_images=[
            make_hero_image(
                "https://example.com/image.jpg"
            )
        ]
    )

    evaluator._resolve_destination = MagicMock(
        return_value={
            "destination": "new york city",
            "country": "united states",
            "country_code": "US",
        }
    )

    evaluator._validate_hero_images_with_gemini = MagicMock(
        side_effect=RuntimeError(
            "Gemini unavailable"
        )
    )

    issues, recommendations, score = (
        evaluator._validate_hero_images(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert issues == []
    assert recommendations == []
    assert score == 100


def test_validate_hero_images_with_gemini_returns_structured_result(
    monkeypatch,
):
    """
    Test the actual Gemini-wrapper method without making a real API call.

    This verifies that:
        - images are converted to Gemini parts
        - Gemini generate_content is called
        - the parsed structured response is returned
    """

    gemini_client = MagicMock()

    parsed_result = HeroImageValidationLLMResult(
        results=[
            HeroImageValidationItem(
                image_index=0,
                status="valid",
                detected_location="New York City",
                reason="Recognizable NYC landmark.",
            )
        ]
    )

    response = SimpleNamespace(
        parsed=parsed_result
    )

    gemini_client.models.generate_content.return_value = response

    evaluator = make_evaluator(
        gemini_client=gemini_client
    )

    # Mock image conversion so no network request occurs.
    evaluator._image_to_gemini_part = MagicMock(
        return_value="FAKE_IMAGE_PART"
    )

    # Mock Gemini SDK Part.from_text.
    monkeypatch.setattr(
        "evaluator.evaluators.knowledge_validation.types.Part.from_text",
        lambda text: f"TEXT_PART:{text}",
    )

    hero_images = [
        make_hero_image(
            "https://example.com/nyc.jpg"
        )
    ]

    result = evaluator._validate_hero_images_with_gemini(
        user_prompt="Create a travel page about New York City",
        destination="new york city",
        hero_images=hero_images,
    )

    assert isinstance(
        result,
        HeroImageValidationLLMResult,
    )

    assert result.results[0].status == "valid"

    gemini_client.models.generate_content.assert_called_once()

    call_kwargs = (
        gemini_client.models.generate_content.call_args.kwargs
    )

    assert (
        call_kwargs["model"]
        == "gemini-3.1-flash-lite"
    )


def test_data_uri_to_gemini_part(monkeypatch):
    """
    Data-URI images should be decoded into Gemini byte parts.
    """

    fake_part = object()

    monkeypatch.setattr(
        "evaluator.evaluators.knowledge_validation.types.Part.from_bytes",
        lambda data, mime_type: (
            fake_part,
            data,
            mime_type,
        ),
    )

    data_uri = (
        "data:image/png;base64,"
        "aGVsbG8="
    )

    result = (
        KnowledgeValidationEvaluator._data_uri_to_part(
            data_uri
        )
    )

    assert result[0] is fake_part
    assert result[1] == b"hello"
    assert result[2] == "image/png"


def test_image_to_gemini_part_rejects_unsupported_source():
    """
    Unsupported image sources should return None.

    Example:
        /static/images/hero.jpg

    The current implementation only accepts:
        - data:image/...
        - http://...
        - https://...
    """

    image = make_hero_image(
        "/static/images/hero.jpg"
    )

    result = (
        KnowledgeValidationEvaluator._image_to_gemini_part(
            image
        )
    )

    assert result is None



def test_property_card_exact_destination_match_is_valid():
    """
    A property whose city exactly matches the requested destination
    should be deterministically valid.
    """

    evaluator = make_evaluator()

    card = make_property_card(
        city="New York City"
    )

    destinations = [{
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }]

    decision = evaluator._deterministic_card_match(
        card,
        destinations,
    )

    assert decision == "valid"


def test_property_card_country_mismatch_is_context_mismatch():
    """
    Different ISO country codes are an immediate mismatch.

    Example:
        Destination: New York City, US
        Property: Paris, France
    """

    evaluator = make_evaluator()

    card = make_property_card(
        city="Paris",
        location="Paris, France",
        country="France",
        country_code="FR",
    )

    destinations = [{
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }]

    decision = evaluator._deterministic_card_match(
        card,
        destinations,
    )

    assert decision == "context_mismatch"


def test_property_card_same_location_substring_is_valid():
    """
    A location containing the intended destination should be accepted
    by the deterministic matcher.

    Example:
        destination = New York City
        location = New York City, NY, USA
    """

    evaluator = make_evaluator()

    card = make_property_card(
        city="New York",
        location="New York City, NY, USA",
    )

    destinations = [{
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }]

    decision = evaluator._deterministic_card_match(
        card,
        destinations,
    )

    assert decision == "valid"


def test_property_card_unknown_geography_is_ambiguous():
    """
    If the country and city cannot be safely matched, the card should
    be sent to the LLM/Tavily verification path.
    """

    evaluator = make_evaluator()

    card = make_property_card(
        city="Flushing",
        location="Queens, New York",
        country="United States",
        country_code="US",
    )

    destinations = [{
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }]

    decision = evaluator._deterministic_card_match(
        card,
        destinations,
    )

    assert decision == "ambiguous"


def test_build_card_search_query_excludes_property_title():
    """
    Property-card search must focus on geographic information.

    The current implementation deliberately excludes:
        - card.title
        - card.property_type
    """

    card = make_property_card(
        title="NYC Luxury Getaway",
        city="Jersey City",
        location="Jersey City, NJ",
        country="United States",
        country_code="US",
    )

    destinations = [{
        "destination": "new york city",
        "country": "united states",
        "country_code": "US",
    }]

    query = (
        KnowledgeValidationEvaluator._build_card_search_query(
            card,
            destinations,
        )
    )

    assert "Jersey City" in query
    assert "new york city" in query.lower()

    assert "NYC Luxury Getaway" not in query
    assert "hotel" not in query.lower()


def test_verify_ambiguous_card_valid_when_llm_returns_valid(
    evaluator,
    content,
    user_prompt,
    destination,
    card,
):
    evaluator._resolve_country_identity = Mock(
        return_value={
            "country": "United States",
            "country_code": "US",
        }
    )

    structured_llm = Mock()

    structured_llm.invoke.return_value = (
        PropertyCardValidationLLMResult(
            status="valid",
            reason=(
                "The property belongs to the requested "
                "destination."
            ),
        )
    )

    evaluator.llm.with_structured_output.return_value = (
        structured_llm
    )

    evaluator._collect_single_card_evidence = Mock(
        return_value="Jersey City is geographically near New York City."
    )

    issue, recommendation = evaluator._verify_ambiguous_card(
        content=content,
        user_prompt=user_prompt,
        destinations=[destination],
        index=0,
        card=card,
    )

    assert issue is None
    assert recommendation is None


def test_verify_ambiguous_card_creates_issue_when_llm_mismatches(
    evaluator,
    content,
    user_prompt,
    destination,
    card,
):
    evaluator._resolve_country_identity = Mock(
        return_value={
            "country": "United States",
            "country_code": "US",
        }
    )

    structured_llm = Mock()

    structured_llm.invoke.return_value = (
        PropertyCardValidationLLMResult(
            status="context_mismatch",
            reason=(
                "Jersey City is an independent municipality "
                "outside New York City."
            ),
        )
    )

    evaluator.llm.with_structured_output.return_value = (
        structured_llm
    )

    evaluator._collect_single_card_evidence = Mock(
        return_value=(
            "Jersey City is an independent municipality "
            "in New Jersey."
        )
    )

    issue, recommendation = evaluator._verify_ambiguous_card(
        content=content,
        user_prompt=user_prompt,
        destinations=[destination],
        index=0,
        card=card,
    )

    assert issue is not None
    assert recommendation is not None

    assert issue.title == "Property Card Context Mismatch"
    assert "Jersey City" in issue.description

    assert recommendation.title == "Review Property Card"


def test_property_card_validation_scores_only_valid_cards():
    """
    Two cards:
        1. New York City -> valid
        2. Paris -> deterministic mismatch

    Expected:
        1/2 valid = 50
    """

    evaluator = make_evaluator()

    evaluator._resolve_destinations = MagicMock(
        return_value=[{
            "destination": "new york city",
            "country": "united states",
            "country_code": "US",
        }]
    )

    valid_card = make_property_card(
        title="NYC Hotel",
        city="New York City",
        location="New York City, NY, USA",
        country="United States",
        country_code="US",
    )

    invalid_card = make_property_card(
        title="Paris Hotel",
        city="Paris",
        location="Paris, France",
        country="France",
        country_code="FR",
    )

    content = make_content(
        property_cards=[
            valid_card,
            invalid_card,
        ]
    )

    issues, recommendations, score = (
        evaluator._validate_property_cards(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert score == 50

    assert len(issues) == 1
    assert len(recommendations) == 1

    assert issues[0].title == (
        "Property Card Context Mismatch"
    )

    assert recommendations[0].title == (
        "Review Property Card"
    )


def test_property_card_validation_returns_100_when_no_cards():
    """No property cards means property-card validation is skipped."""

    evaluator = make_evaluator()

    content = make_content(
        property_cards=[]
    )

    issues, recommendations, score = (
        evaluator._validate_property_cards(
            content=content,
            user_prompt="Create a travel page about New York City",
        )
    )

    assert issues == []
    assert recommendations == []
    assert score == 100


# FINAL SCORE INTEGRATION

def test_final_score_is_minimum_of_general_card_and_image_scores():
    """
    Final knowledge score uses the minimum score across active
    validation dimensions.

    Example:
        General knowledge = 90
        Property cards = 50
        Hero images = 0

        Final = 0
    """

    evaluator = make_evaluator(
        gemini_client=MagicMock()
    )

    evaluator._analyze = MagicMock(
        return_value=make_general_llm_result(
            score=90
        )
    )

    evaluator._validate_property_cards = MagicMock(
        return_value=(
            [],
            [],
            50,
        )
    )

    evaluator._validate_hero_images = MagicMock(
        return_value=(
            [],
            [],
            0,
        )
    )

    content = make_content(
        property_cards=[
            make_property_card()
        ],
        hero_images=[
            make_hero_image(
                "https://example.com/image.jpg"
            )
        ],
    )

    result = evaluator.evaluate(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    assert result.score == 0


def test_final_score_without_cards_or_hero_images_uses_general_score():
    """
    If there are no property cards and no hero images, the final score
    should be the general knowledge score.
    """

    evaluator = make_evaluator(
        gemini_client=None
    )

    evaluator._analyze = MagicMock(
        return_value=make_general_llm_result(
            score=88
        )
    )

    evaluator._validate_property_cards = MagicMock(
        return_value=(
            [],
            [],
            100,
        )
    )

    evaluator._validate_hero_images = MagicMock(
        return_value=(
            [],
            [],
            100,
        )
    )

    content = make_content(
        property_cards=[],
        hero_images=[],
    )

    result = evaluator.evaluate(
        content=content,
        user_prompt="Create a travel page about New York City",
    )

    assert result.score == 88


# ISSUE SEVERITY


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "High"),
        (39, "High"),
        (40, "Medium"),
        (69, "Medium"),
        (70, "Low"),
        (100, "Low"),
    ],
)
def test_issue_severity(score, expected):
    """Verify score-to-severity mapping."""

    assert (
        KnowledgeValidationEvaluator._issue_severity(
            score
        )
        == expected
    )