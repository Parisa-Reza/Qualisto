# Knowledge Validation Architecture

## Overview

The Knowledge Validation module checks whether an AI-generated travel webpage contains information that is factually reasonable and relevant to the destination requested by the user.

It has **four** separate validation paths:

* **General Knowledge Validation**
  * Validates the overall webpage content.
  * Checks factual accuracy, destination relevance, contradictions, unsupported claims, and content belonging to another destination.

* **Property Card Validation**
  * Validates whether individual property cards geographically belong to the requested destination.
  * Uses deterministic checks first.
  * Only sends unclear cases to Tavily and the LLM.

* **Hero Image Validation**
  * Validates whether hero-section images are geographically compatible with the requested destination.
  * Uses a multimodal LLM (Gemini) that can actually look at the images, since this is the only path that requires vision rather than text evidence.

* **Property Type Tabs Validation**
  * Validates that the actual property types listed under a specific tab (e.g., "Villas", "Cottages", "Apartments") match the label of that tab.
  * Uses simple deterministic string normalization and equality checks (no LLM calls).

The final result combines whichever paths apply. General Knowledge Validation always runs. Property Card Validation only contributes if property cards exist. Hero Image Validation only contributes if hero images exist and can be validated. Property Type Tabs Validation only contributes if property type tabs exist. The final Knowledge Validation score is the **minimum** score across every path that actually ran.

## High-Level Flow

```text
USER PROMPT + EXTRACTED WEBSITE CONTENT
                    |
                    v
         KNOWLEDGE VALIDATION EVALUATOR
                    |
        +-----------+-----------+-----------+------------+
        |           |           |           |            |
        v           v           v           v            v
GENERAL      PROPERTY CARD  HERO IMAGE   PROPERTY TYPE   (Final)
KNOWLEDGE    VALIDATION    VALIDATION   TABS VALIDATION  Score
VALIDATION   (parallel)    (batched)    (deterministic)  |
        |           |           |           |            |
        +-----------+-----------+-----------+------------+
                    |
                    v
     FINAL SCORE = MIN of every score
     from a path that actually ran
                    |
                    v
      ISSUES + RECOMMENDATIONS + FINAL SCORE


## Work flowchart

START: evaluate(content, user_prompt)
  │
  ▼
1️⃣ RUN GENERAL KNOWLEDGE VALIDATION (_analyze)
   │
   ├─ Collect search evidence via Tavily (_collect_search_evidence)
   │   └─ Query: user_prompt + page title 
   │
   ├─ Build prompt with content  + evidence
   │
   ├─ Call LLM with structured output → KnowledgeValidationLLMResult
   │   ├─ score (0–100)
   │   ├─ verified_claims, unsupported_claims, uncertain_claims
   │   └─ findings (list of KnowledgeFinding with issue + recommendation)
   │
   └─ Issues/Recommendations from findings are stored for later.

   └──▶ Proceed to hero images (step 2)

─────────────────────────────────────────────────────────────

2️⃣ HERO IMAGE VALIDATION (_validate_hero_images)
   │
   ├─ Does content have hero_images list?
   │   │
   │   ├─ NO  → Skip, set image_score = 100, no issues
   │   │
   │   └─ YES → Is Gemini client configured?
   │       │
   │       ├─ NO  → Skip, set image_score = 100, no issues
   │       │
   │       └─ YES → Resolve SINGLE destination from user prompt
   │           │    (_resolve_destination → first from list)
   │           │
   │           ├─ If no destination resolved → Skip, score=100
   │           │
   │           └─ Else, for each hero image:
   │               │
   │               ├─ Convert image to a Part (data URI or remote URL)
   │               │   └─ If fails to fetch → skip that image (log warning)
   │               │
   │               ├─ Send prompt + all image parts to Gemini
   │               │   (prompt asks to classify each image as valid / context_mismatch / uncertain)
   │               │
   │               └─ For each result:
   │                   ├─ "valid"          → count as valid
   │                   ├─ "uncertain"      → count as uncertain (no issue)
   │                   └─ "context_mismatch" → create High‑severity issue
   │                         (image shows wrong destination)
   │
   ├─ Compute image_score = (total_images - mismatches) / total * 100
   │
   └──▶ Proceed to property cards (step 3)

─────────────────────────────────────────────────────────────

3️⃣ PROPERTY CARD DESTINATION VALIDATION (_validate_property_cards)
   │
   ├─ Does content have property_cards list?
   │   │
   │   ├─ NO  → Skip, set card_score = 100, no issues
   │   │
   │   └─ YES → Resolve ALL destinations from user prompt
   │           (_resolve_destinations – uses deterministic list parsing first,
   │            fallback to LLM extraction)
   │       │
   │       ├─ If no destinations resolved → Skip, card_score=100, no issues
   │       │
   │       └─ For EACH property card:
   │           │
   │           ▼
   │           Run DETERMINISTIC MATCH (_deterministic_card_match)
   │           against the entire list of destinations.
   │           │
   │           └─ For each destination, call _match_single_destination:
   │               │
   │               ├─ 1️⃣ COUNTRY CODE CHECK (strict ISO, case‑insensitive)
   │               │   │
   │               │   ├─ If BOTH card.country_code AND dest.country_code exist AND they differ
   │               │   │   └─ ▶ return "context_mismatch" (city is never checked)
   │               │   │
   │               │   └─ Else (one missing or equal) → proceed to city check
   │               │
   │               ├─ 2️⃣ CITY NAME CHECK (card.city vs dest.destination)
   │               │   │
   │               │   └─ Check in order (first match wins):
   │               │       ├─ Exact match                 → "valid"
   │               │       ├─ Substring (one contains the other) → "valid"
   │               │       │   (e.g. "new york" in "new york city")
   │               │       ├─ Word‑prefix match            → "valid"
   │               │       │   (e.g. dest="new york", card="new" → match)
   │               │       └─ None of above → proceed to location check
   │               │
   │               ├─ 3️⃣ LOCATION FALLBACK (card.location)
   │               │   │
   │               │   └─ If dest.destination is a substring of card.location
   │               │       └─ ▶ "valid"
   │               │
   │               └─ 4️⃣ No match, no mismatch → return "ambiguous"
   │
           After checking against ALL destinations, combine the statuses:
           │
           ├─ If ANY status == "valid"            → overall = "valid"    (card is good)
           ├─ If ALL statuses == "context_mismatch" → overall = "context_mismatch"
           │                                        (immediate issue, no further checks)
           └─ Else (mix of mismatch + ambiguous, or only ambiguous)
                                                    overall = "ambiguous"

           └──▶ For cards with overall = "valid":
           │      → count as valid, no issue.
           │
           └──▶ For cards with overall = "context_mismatch":
           │      → Create HIGH severity issue:
           │        "The property's country does not match any requested destination."
           │        (No LLM call, no search)
           │
           └──▶ For cards with overall = "ambiguous":
           │      → Enter DEEP VALIDATION (parallel processing)
           │         (_verify_ambiguous_cards_parallel)
           │         │
           │         ├─ For each ambiguous card:
           │         │   │
           │         │   ├─ Resolve card's country identity (_resolve_country_identity)
           │         │   │   ├─ Uses LLM + search (Tavily) if country or code missing
           │         │   │   └─ If resolved code not in any destination's codes → 
           │         │   │       ▶ raise mismatch (issue, skip LLM)
           │         │   │
           │         │   ├─ If country is OK, collect external evidence
           │         │   │   via Tavily (_collect_single_card_evidence)
           │         │   │   Query: Is "{card_city}" part of any destination?
           │         │   │
           │         │   ├─ Call LLM with strict prompt (_build_property_card_prompt)
           │         │   │   (only decides if city is legally/administratively inside
           │         │   │    any intended destination – ignores metro areas)
           │         │   │
           │         │   └─ If LLM returns "valid" → card becomes valid (counted)
           │         │       If "context_mismatch" → create issue with reason
           │         │
           │         └─ After all processed, cards that became valid are added to valid count.
           │
           └──▶ Compute card_score = (valid_cards / total_cards) * 100

   └──▶ Proceed to property type tabs (step 4)

─────────────────────────────────────────────────────────────

4️⃣ PROPERTY TYPE TABS VALIDATION (_validate_property_type_tabs)
   │
   ├─ Does content have property_type_tabs list?
   │   │
   │   ├─ NO  → Skip, set property_type_score = 100, no issues
   │   │
   │   └─ YES → For each tab:
   │       │
   │       ├─ Expected type = tab.tab_name (normalized)
   │       │
   │       └─ For each actual property_type in tab.property_types:
   │           │
   │           ├─ If normalized(actual) == expected → count as valid
   │           │
   │           └─ Else → create HIGH severity issue:
   │               "The '{tab_name}' tab contains a '{actual}' property."
   │               Recommendation: tab should contain only its own type.
   │
   ├─ Compute property_type_score = (valid / total) * 100
   │
   └──▶ Proceed to final scoring (step 5)

─────────────────────────────────────────────────────────────

5️⃣ FINAL SCORE CALCULATION
   │
   ├─ Gather all scores:
   │   - general_score (from step 1)
   │   - image_score   (from step 2, default 100 if skipped)
   │   - card_score    (from step 3, default 100 if skipped)
   │   - property_type_score (from step 4, default 100 if skipped)
   │
   └─ final_score = MIN( all available scores )

   └──▶ Return KnowledgeValidationResult with:
       - final_score
       - all issues collected from all modules
       - all recommendations
       - verified/unsupported/uncertain claims (from general)

─────────────────────────────────────────────────────────────
END

```
| Scenario | How the code handles it | Example |
|----------|--------------------------|---------|
| User prompt is a structured list | `_extract_destination_candidates` detects quoted, line‑separated, or paired‑comma lists and parses them deterministically – no LLM for segmentation. | `"Paris, France", "Lyon, France"` → parsed as two entries. |
| Prompt is free text | Falls back to `_resolve_destinations_via_llm` – the LLM extracts all destinations. | `"Best hotels in Paris and Rome"` → LLM returns two destinations. |
| Country code missing in extracted destination | Calls `_resolve_country_identity` with search + LLM to resolve. | Input: `"Dunmore Town"` (no country) → resolves to Bahamas → `"BS"`. |
| Card has a country code, destination has one, and they differ | Immediate `"context_mismatch"` – city is never checked. | Card code = `"US"`, dest code = `"BS"` → ❌ mismatch. |
| Card country code missing, but city matches | Passes country check (skipped) → city check sees exact match → `"valid"`. | Card: city=`"Paris"`, no code; dest: city=`"Paris"`, code=`"FR"` → ✅ valid. |
| Card city is a substring/alias | Uses substring and prefix matching – accepts as valid without LLM. | Dest: `"New York"`, Card city: `"New York City"` → valid. |
| Card location contains dest name, but city is empty | The location fallback catches it. | Card: city=`""`, location=`"Downtown Paris, France"` → valid. |
| Ambiguous card after deterministic checks | Goes to LLM with strict rules – only accepts if legally/administratively inside (no metro areas). | Dest: `"New York"`, card city=`"Brooklyn"` → LLM says valid (borough).<br>Dest: `"New York"`, card city=`"Jersey City"` → LLM says mismatch (independent city). |
| LLM or search fails | Catches exceptions, logs, and creates a generic issue – the card is treated as mismatch. | Tavily timeout → fallback issue: `"The geographic relationship could not be verified."` |
| No property cards | Skipped entirely – card_score defaults to 100, no issues. | Content has no `property_cards` attribute. |
| No hero images | Skipped – image_score = 100, no issues. | `hero_images` empty or missing. |
| Gemini not configured | Skipped – no image validation. | `gemini_client` is `None`. |
| Property type tabs mismatch | Every mismatched actual type creates an issue. | Tab named `"Cottages"` contains a `"Villa"` → issue. |
| Multiple destinations – card matches any one | `any(s == "valid")` → overall valid. | Destinations: [Paris, Rome]; card city=Paris → valid. |
| Card mismatches all destinations' countries | `all(s == "context_mismatch")` → immediate issue. | Dest codes: [US, IT]; card code=FR → all mismatch → issue. |
```
