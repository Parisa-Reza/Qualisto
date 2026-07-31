from pydantic import BaseModel, Field
from evaluator.claim_extractor.claim_extractor import ClaimExtractor
from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import EvaluationResult, Issue, KnowledgeValidationResult, Recommendation


class ClaimValidationLLMResult(BaseModel):
    status: str = Field(description="verified, unsupported, or uncertain")
    reason: str

class PropertyCardValidationLLMResult(BaseModel):
    status: str = Field(description="valid or context_mismatch")
    reason: str


class KnowledgeValidationEvaluator:
    def __init__(self, llm, search_client):
        self.llm = llm
        self.search_client = search_client

    def evaluate(self, content: WebsiteContent) -> KnowledgeValidationResult:
        claims = ClaimExtractor.extract(content.plain_text)
        verified_claims = []
        unsupported_claims = []
        uncertain_claims = []
        issues = []
        recommendations = []

   
        for claim in claims:
            evidence = self.search_client.search(claim, max_results=5)
            result = self._validate_claim(claim, evidence)

            if result.status == "verified":
                verified_claims.append(claim)
            elif result.status == "unsupported":
                unsupported_claims.append(claim)
                issues.append(Issue(severity="High", title="Unsupported Claim", description=f"{claim} Reason: {result.reason}"))
                recommendations.append(Recommendation(title="Verify Factual Claim", description=f"Review and verify this claim: {claim}"))
            else:
                uncertain_claims.append(claim)
                issues.append(Issue(severity="Medium", title="Uncertain Claim", description=f"{claim} Reason: {result.reason}"))
                recommendations.append(Recommendation(title="Review Uncertain Claim", description=f"Check reliable sources for: {claim}"))

      
        card_issues, card_recommendations = self._validate_property_cards(content)
        issues.extend(card_issues)
        recommendations.extend(card_recommendations)

        score = self._calculate_score(len(claims), len(unsupported_claims), len(uncertain_claims))

        
        score = max(0, score - (len(card_issues) * 15))

        return KnowledgeValidationResult(score=score, issues=issues, recommendations=recommendations, verified_claims=verified_claims, unsupported_claims=unsupported_claims, uncertain_claims=uncertain_claims)

    def _validate_claim(self, claim: str, evidence: list[dict]) -> ClaimValidationLLMResult:
        structured_llm = self.llm.with_structured_output(ClaimValidationLLMResult)
        return structured_llm.invoke(self._build_prompt(claim, evidence))

    # NEW: validate every extracted property card.
    def _validate_property_cards(self, content: WebsiteContent):
        issues = []
        recommendations = []

        for card in content.property_cards:
            result = self._validate_property_card(content, card)

            if result.status == "context_mismatch":
                issues.append(Issue(severity="High", title="Property Card Context Mismatch", description=(f"Property '{card.title}' is located in {card.location}. {result.reason}")))
                recommendations.append(Recommendation(title="Review Property Card", description=(f"Remove or replace '{card.title}' because its location does not match the webpage destination.")))

        return issues, recommendations

   
    def _validate_property_card(self, content: WebsiteContent, card) -> PropertyCardValidationLLMResult:
        structured_llm = self.llm.with_structured_output(PropertyCardValidationLLMResult)
        return structured_llm.invoke(self._build_property_card_prompt(content, card))

  
    @staticmethod
    def _build_property_card_prompt(content: WebsiteContent, card) -> str:
        headings = []
        for heading_list in (content.headings.h1, content.headings.h2, content.headings.h3):
            headings.extend(heading_list)

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
Usually valid because Jersey City is directly relevant
to the New York City travel area.

New York City page + Paris, France:
Context mismatch.

Rules:
- Return "valid" when the property is reasonably relevant
  to the page destination.
- Return "context_mismatch" when it clearly belongs to
  another destination.
- Do not reject a property merely because it is in a
  nearby city or metropolitan area.
- Do not evaluate HTML quality.
- Do not evaluate SEO.
- Do not evaluate keyword density.
- Do not invent facts.

Return the required structured result.
"""

    @staticmethod
    def _build_prompt(claim: str, evidence: list[dict]) -> str:
        sources = "\n\n".join((f"TITLE: {item.get('title', '')}\nURL: {item.get('url', '')}\nCONTENT: {item.get('content', '')}") for item in evidence)

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
    def _calculate_score(total_claims, unsupported, uncertain):
        if total_claims == 0:
            return 100
        penalty = unsupported * 20 + uncertain * 10
        return max(0, 100 - penalty)