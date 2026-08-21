# Knowledge Validation Architecture

## Overview

The Knowledge Validation module checks whether an AI-generated travel webpage contains information that is factually reasonable and relevant to the destination requested by the user.

It has three separate validation paths:

* **General Knowledge Validation**

  * Validates the overall webpage content
  * Checks factual accuracy, destination relevance, contradictions, unsupported claims, and content belonging to another destination

* **Property Card Validation**

  * Validates whether individual property cards geographically belong to the requested destination
  * Uses deterministic checks first
  * Only sends unclear cases to Tavily and the LLM

* **Hero Image Validation**

  * Validates whether hero-section images are geographically compatible with the requested destination
  * Uses a multimodal LLM (Gemini) that can actually look at the images, since this is the only path that requires vision rather than text evidence

The final result combines whichever paths apply. General Knowledge Validation always runs. Property Card Validation only contributes if property cards exist. Hero Image Validation only contributes if hero images exist and can be validated. The final Knowledge Validation score is the **minimum** score across every path that actually ran.

## High-Level Flow

```text
USER PROMPT + EXTRACTED WEBSITE CONTENT
                    |
                    v
         KNOWLEDGE VALIDATION EVALUATOR
                    |
        +-----------+-----------+-----------+
        |                       |           |
        v                       v           v
GENERAL KNOWLEDGE       PROPERTY CARD   HERO IMAGE
VALIDATION              VALIDATION      VALIDATION
        |                       |           |
        |                       v           v
        |              RESOLVE DESTINATION (shared)
        |                       |           |
        |                 LLM CALL #1       |
        |                       |           |
        |              Destination + Country|
        |              + ISO Country Code   |
        |                       |           |
        |              Country Identity     |
        |              Resolution           |
        |                       |           |
        |                 Tavily Search     |
        |                       |           |
        |                 LLM CALL #2       |
        |                       |           |
        |              Canonical Country    |
        |              Identity             |
        |                       |           |
        |         Deterministic Card Checks |
        |                       |           v
        |             +---------+------+   Convert hero images
        |             |         |      |   to Gemini parts
        |           Valid   Mismatch Ambiguous  |
        |             |         |      |         v
        |             |         |      v   Single Gemini call
        |             |         | THREADPOOL     |
        |             |         | Parallel       v
        |             |         | Validation   valid /
        |             |         |      |     context_mismatch /
        |             |         |      |       uncertain
        |             |         |      v         |
        |             |         | Tavily Search  v
        |             |         |      |    IMAGE SCORE
        |             |         | LLM CALL
        |             |         |      |
        |             |         | Valid / Mismatch
        |             +---------+------+
        |                       |
        |                 CARD SCORE
        |                       |
        v                       |               |
    Tavily Search                |               |
        |                       |               |
        v                       |               |
    LLM CALL                    |               |
        |                       |               |
        v                       v               v
 GENERAL SCORE          PROPERTY CARD SCORE  IMAGE SCORE
        |                       |               |
        +-----------+-----------+---------------+
                    |
                    v
     FINAL SCORE = MIN of every score
     from a path that actually ran
                    |
                    v
      ISSUES + RECOMMENDATIONS + FINAL SCORE
```

---

# 1. General Knowledge Validation

## Purpose

This path validates the webpage as a whole.

The evaluator checks whether the content:

* Matches the destination and subject requested in the original user prompt
* Contains incorrect factual claims
* Contains unsupported factual claims
* Contains contradictory claims
* Contains incorrect destination information
* Contains incorrect attraction or location information
* Contains incorrect travel information
* Contains incorrect hotel or property information
* Contains content that belongs to another destination

The original user prompt is treated as the authority for what the webpage is supposed to be about. The webpage title and headings do not override the user's requested destination.

## Flow

```text
EXTRACTED WEBPAGE CONTENT + USER PROMPT
                    |
                    v
        BUILD TAVILY SEARCH QUERY
                    |
                    v
         USER PROMPT + PAGE TITLE
                    |
                    v
              TAVILY SEARCH
              max_results = 5
                    |
                    v
       FORMAT EXTERNAL SEARCH EVIDENCE
                    |
                    v
        BUILD GENERAL VALIDATION PROMPT
                    |
                    v
              LLM CALL
                    |
                    v
       STRUCTURED KnowledgeValidationLLMResult
                    |
                    v
       SCORE + VERIFIED CLAIMS
       + UNSUPPORTED CLAIMS
       + UNCERTAIN CLAIMS
       + ISSUES + RECOMMENDATIONS
```

The general search query is built from:

* The original user prompt
* The webpage title

The query is limited to 400 characters. Tavily returns up to five results, and the result titles, URLs, and snippets are formatted as evidence for the LLM.

## Where the LLM is called

After Tavily evidence is collected, the webpage content, headings, user prompt, and search evidence are passed to the LLM.

The LLM uses structured output based on `KnowledgeValidationLLMResult`.

It returns:

* `score`
* `verified_claims`
* `unsupported_claims`
* `uncertain_claims`
* `issues`
* `recommendations`

The score must be between 0 and 100.

## General Knowledge Scoring

The LLM assigns the general knowledge score using these ranges:

| Score    | Meaning                                 |
| -------- | --------------------------------------- |
| 100      | Accurate and strongly aligned           |
| 80 to 99 | Minor issues                            |
| 60 to 79 | Noticeable issues                       |
| 40 to 59 | Significant issues                      |
| 0 to 39  | Major inaccuracies or wrong destination |

If there is not enough evidence to confidently validate a claim, the claim should be classified as `uncertain` rather than automatically treated as false.

---

# 2. Destination Resolution

Both Property Card Validation and Hero Image Validation first need to understand what destination the user actually requested. This resolver is shared between the two paths so they always agree on what "the destination" means.

For example:

```text
User Prompt:
"Create a travel page for New York City"

Expected destination:
New York City

Expected country:
United States

Expected ISO country code:
US
```

The important rule is that the destination comes from the **user prompt only**.

The system does not use:

* Webpage title
* Webpage headings
* Property card title
* Hotel name
* Property location
* Existing webpage content
* Hero images themselves

to decide what the intended destination is.

## Destination Resolution Flow

```text
USER PROMPT
    |
    v
LLM CALL
    |
    v
Extract:
- destination
- country
- country_code
- explanation
    |
    v
Normalize destination and country
    |
    v
RESOLVE COUNTRY IDENTITY
    |
    +----------------------+
    | Tavily Search        |
    | if country/code      |
    | information exists   |
    +----------------------+
    |
    v
LLM CALL
    |
    v
Canonical Country +
ISO 3166-1 Alpha-2 Code
    |
    v
Country resolved?
    |
   YES --------------------> Continue
    |
    NO
    |
    v
Tavily search using destination
    |
    v
LLM CALL with external evidence
    |
    v
Resolve destination again
    |
    v
Resolve country identity again
    |
    v
RETURN:
destination + country + country_code
```

---

# 3. How Country Resolution Works

Country names can appear in different forms.

For example:

```text
USA
United States
United States of America
```

The code does not depend on a hardcoded mapping table for these examples.

Instead, it dynamically resolves the country representation.

The process uses:

* Country name, if available
* Candidate country code, if available
* Geographic context
* Tavily evidence
* LLM structured output

The LLM is asked to return:

* A canonical country name
* A valid ISO 3166-1 alpha-2 code
* A confidence level of `high`, `medium`, or `low`

The result is rejected if:

* The country is empty
* The country code is empty
* Confidence is `low`

This prevents uncertain country identity from being treated as a confirmed geographic match.

### Example

```text
Input:
country = "USA"
country_code = ""
context = "New York City"

        |
        v

Tavily:
Search for geographic and ISO evidence

        |
        v

LLM:
Resolve canonical country identity

        |
        v

Output:
country = "United States"
country_code = "US"
confidence = "high"
```

The country code is also normalized. Only a two-letter uppercase code matching the pattern `[A-Z]{2}` is accepted as a candidate ISO-style country code. Other values are discarded.

---

# 4. Hero Image Validation

## Purpose

The hero image validator answers a question the other two paths cannot answer on their own:

> Does this hero-section image actually depict the destination requested by the user?

This is the only validation path that requires *vision*, not just text evidence. A generic-sounding sentence can be checked against search results, but a photo can only be judged by something that can look at it — so this path calls a multimodal model (Gemini) instead of the text-only LLM used everywhere else in the evaluator.

## When this path is skipped

Hero image validation is intentionally conservative about producing a false negative. It is skipped (returning a clean score of `100`, with no issues) whenever it cannot make a confident judgment:

* No hero images were extracted from the page
* No `gemini_client` was configured on the evaluator
* The intended destination could not be resolved from the user prompt
* The Gemini call itself fails (network error, malformed response, etc.)
* None of the hero images could be successfully converted into something Gemini can read

In every one of these cases, the evaluator does **not** invent a geographic mismatch — a missing dependency or failed download is not evidence that the images are wrong.

## Flow

```text
HERO IMAGES EXIST?
      NO -> image_score = 100 (skipped)
      YES
        |
GEMINI CLIENT CONFIGURED?
      NO -> image_score = 100 (skipped, warning logged)
      YES
        |
RESOLVE INTENDED DESTINATION
   (same resolver as Property Card Validation)
        |
DESTINATION RESOLVED?
      NO -> image_score = 100 (skipped)
      YES
        |
CONVERT EACH HERO IMAGE TO A GEMINI PART
   data:image/...  -> decode base64 directly
   http(s)://...    -> download with a browser-like
                        User-Agent, confirm/guess
                        Content-Type
   unsupported src  -> skipped + logged, excluded
        |
AT LEAST ONE IMAGE CONVERTED?
      NO -> return empty results, no issues
      YES
        |
ONE BATCHED GEMINI CALL
   all images + strict destination prompt
   response_schema = HeroImageValidationLLMResult
   temperature = 0
        |
FOR EACH IMAGE RESULT:
   valid            -> counted as valid, no issue
   uncertain        -> logged only, does NOT affect score
   context_mismatch -> High-severity Issue +
                        "Review Hero Image" Recommendation
        |
        v
image_score = round(
    (total_images - mismatch_count) / total_images * 100
)
```

## Source-of-truth rule

Exactly like destination resolution, the **user prompt is the only source of truth**. Gemini is explicitly instructed *not* to change the intended destination based on the image itself, the image filename or URL, alt text, the webpage title/headings, body content, or any other image in the batch. Images are evidence to be judged against a destination that has already been decided — never a way to redefine it.

## Status categories

| Status              | Meaning                                                                                                                     |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `valid`              | The image gives reasonable visual evidence that it represents the requested destination.                                    |
| `context_mismatch`   | The image clearly depicts a different, identifiable destination, or contains strong geographic evidence inconsistent with it. |
| `uncertain`          | The image is geographically generic (e.g. a generic beach, hotel room, or sunset) or there isn't enough evidence either way. |

Country-level or visual similarity alone is explicitly not enough to call an image `valid` — an arbitrary beach photo from the right country is not proof that it depicts the specific requested destination.

### Example

```text
Requested destination: Cox's Bazar

Image clearly depicts Bali          -> context_mismatch
Image clearly depicts Saint Martin  -> context_mismatch
Image is a generic tropical beach   -> uncertain
Image plausibly shows Cox's Bazar   -> valid
```

## Image conversion details

Each hero image comes into the validator as whatever the extractor captured (`image.src`), and is converted into a Gemini-compatible `Part` before it can be sent:

* **`data:image/...` URIs** are decoded directly — the MIME type comes from the header, the bytes come from base64-decoding the payload.
* **`http://` / `https://` URLs** are downloaded with `requests`, sending a browser-like `User-Agent` header so image hosts that block generic scripted clients are less likely to reject the request. If the response's `Content-Type` header isn't a clean `image/*` value, the code falls back to guessing the MIME type from the URL's file extension before giving up.
* **Anything else** (empty src, unrecognized scheme) is skipped and logged as a warning.
* A failure at any point (bad download, corrupt base64, non-image response) is caught, logged, and that single image is simply excluded from the batch — it does not fail the whole evaluation.

If none of the hero images survive this conversion step, Gemini is never called, and no results or issues are produced for that page.

## Scoring

Only confirmed `context_mismatch` results reduce the score. `uncertain` results are surfaced for visibility (via a log warning) but are deliberately excluded from the score calculation, so the validator never penalizes a page just because an image was too generic to judge with confidence.

```text
image_score = round(
    (total_images - mismatch_count) / total_images * 100
)
```

### Example

```text
Total hero images: 5
Mismatched: 1
Uncertain: 1
Valid: 3

image_score = round((5 - 1) / 5 * 100) = 80
```

---

# 5. Property Card Validation

## Purpose

The property card validator answers a more specific question:

> Does this property geographically belong to the destination requested by the user?

It does not evaluate:

* Property quality
* Price
* Amenities
* Images
* SEO
* HTML
* Readability
* Writing style

The focus is geographic context.

## Property Card Flow

```text
PROPERTY CARDS EXIST?
      |
   NO |-----------------> Return card score = 100
      |
   YES
      |
      v
RESOLVE INTENDED DESTINATION
      |
      v
FOR EACH PROPERTY CARD
      |
      v
DETERMINISTIC PRE-CHECK
      |
      +----------+-----------+
      |          |           |
    VALID    MISMATCH    AMBIGUOUS
      |          |           |
      |          |           v
      |          |    Send to ThreadPool
      |          |    for parallel validation
      |          |           |
      |          |           v
      |          |   Resolve card country
      |          |           |
      |          |       Tavily Search
      |          |           |
      |          |        LLM CALL
      |          |           |
      |          |     Valid / Mismatch
      |          |           |
      +----------+-----------+
                 |
                 v
          COUNT VALID CARDS
                 |
                 v
   CARD SCORE = VALID / TOTAL × 100
```

If no property cards exist, the method returns a property card score of `100`. However, because the final score uses the general score when there are no cards, this `100` does not artificially increase the final Knowledge Validation score.

---

# 6. Deterministic Property Card Checks

The first validation stage is deliberately simple and deterministic.

The system checks the card without calling the LLM when there is enough information to make a safe decision.

A card can receive one of three outcomes:

* `valid`
* `context_mismatch`
* `ambiguous`

## Country Code Mismatch

If both the intended destination and property card have valid country codes, and the codes differ:

```text
Destination country code: US
Property country code: FR

Result:
context_mismatch
```

No LLM call is needed.

## Direct City Match

If the intended destination and property city match after normalization:

```text
Destination: New York City
Property city: New York City

Result:
valid
```

The code also supports certain normalized prefix-style comparisons.

## Location Contains Destination

If the normalized intended destination appears in the property location:

```text
Destination: New York City
Property location: Manhattan, New York City, NY

Result:
valid
```

## Otherwise

If the deterministic checks cannot safely prove either a match or mismatch:

```text
Result:
ambiguous
```

The card is sent to the more expensive validation path.

---

# 7. Why ThreadPoolExecutor Is Used

Ambiguous property cards may each require:

* Country identity resolution
* Tavily searches
* LLM calls

Processing these cards one at a time would be slow.

The code therefore uses:

```python
ThreadPoolExecutor(max_workers=self.max_workers)
```

The default `max_workers` value is `4`.

Each ambiguous card is submitted as a separate task. The executor processes multiple cards concurrently, and `as_completed()` collects results as individual tasks finish.

> **Note:** this pattern is specific to Property Card Validation. Hero Image Validation does *not* use a thread pool — all hero images for a page are sent together in a single batched multimodal Gemini call instead of one call per image.

## Example

Suppose the page contains five cards:

```text
Card 1: Manhattan        -> deterministic valid
Card 2: Jersey City      -> deterministic ambiguous
Card 3: Flushing         -> deterministic ambiguous
Card 4: Paris            -> deterministic mismatch
Card 5: Brooklyn         -> deterministic ambiguous
```

The system does this:

```text
Card 1 -> valid immediately
Card 4 -> mismatch immediately

Cards 2, 3, 5
        |
        v
ThreadPoolExecutor
        |
        +---- Worker 1 -> Validate Card 2
        |
        +---- Worker 2 -> Validate Card 3
        |
        +---- Worker 3 -> Validate Card 5
```

The system does not wait for Card 2 to completely finish before starting Card 3 and Card 5.

This is particularly useful because Tavily and LLM calls are external operations and may spend time waiting for responses.

---

# 8. Ambiguous Property Card Validation

Each ambiguous card goes through a deeper validation process.

## Step 1: Resolve the Property Card Country

The card's:

* `country`
* `country_code`
* `city`
* `location`

are used to resolve its canonical country identity.

This can involve:

```text
Tavily Search
        +
LLM Structured Output
```

If the resolved property country code clearly differs from the intended destination country code, the card is immediately marked as a context mismatch.

## Step 2: Collect Geographic Evidence

If country identity does not prove a mismatch, the system builds a geographic query.

The query is based on:

* Property city
* Property location
* Property country
* Intended destination
* Intended destination country

The property title and property type are intentionally excluded because marketing text can pollute search results and should not be treated as geographic evidence.

Example:

```text
Property city:
Flushing

Property location:
Queens, NY

Destination:
New York City

Tavily question:
Is "Flushing" (Queens, NY) part of the city of
"New York City", United States?
administrative boundaries city limits
```

## Step 3: LLM Geographic Decision

The LLM receives:

* Original user prompt
* Intended destination
* Property city
* Property location
* Tavily geographic evidence

The LLM returns only:

```text
valid
```

or:

```text
context_mismatch
```

The LLM follows a strict decision order:

1. Same city name or a common alias for the same city
2. Officially recognized neighborhood, borough, ward, or district legally inside the destination
3. Independent municipality, town, or city with separate local government
4. Ambiguous, conflicting, or insufficient evidence

Examples built into the validation prompt include:

```text
Destination: New York City
Property: Flushing, NY
Result: valid

Reason:
Flushing is treated as part of NYC through Queens.
```

```text
Destination: New York City
Property: Jersey City, NJ
Result: context_mismatch

Reason:
Jersey City is an independent municipality and being part
of the NYC metropolitan area is not enough.
```

The validator explicitly rejects geographic reasoning based only on:

* Being nearby
* Being in the same metropolitan area
* Shared airport
* Marketing association

---

# 9. Property Card Scoring

After all deterministic and ambiguous cards have been processed:

```text
card_score = round(
    (valid_count / total_cards) * 100
)
```

Example:

```text
Total cards: 10
Valid cards: 8

Card Score:
(8 / 10) × 100 = 80
```

Cards with a context mismatch are not included in the valid count.

If an ambiguous card is successfully validated, it is added to the valid cards.

If the card cannot be verified or fails validation, an issue and recommendation are generated and it does not contribute to the valid count.

---

# 10. Final Knowledge Validation Scoring

The system can produce up to three scores:

```text
General Knowledge Score   (always computed)
Property Card Score       (only if property cards exist)
Hero Image Score          (only if hero images exist and were validated)
```

The final scoring logic is:

```text
scores = [General Knowledge Score]

IF property cards exist:
    scores.append(Property Card Score)

IF hero images exist:
    scores.append(Hero Image Score)

Final Score = min(scores)
```

This is intentionally conservative. A webpage should not receive a high Knowledge Validation score just because some validation paths perform well while another reveals serious problems.

### Example 1 — property cards only

```text
General Knowledge Score: 92
Property Card Score: 40

Final Score:
min(92, 40) = 40
```

The general text may be mostly correct, but many property cards are geographically wrong.

### Example 2 — property cards only

```text
General Knowledge Score: 55
Property Card Score: 100

Final Score:
min(55, 100) = 55
```

All property cards may be correct, but the general webpage content still contains significant knowledge problems.

### Example 3 — no property cards, no hero images

```text
General Knowledge Score: 82

Final Score:
82
```

### Example 4 — all three paths present

```text
General Knowledge Score: 88
Property Card Score: 75
Hero Image Score: 60

Final Score:
min(88, 75, 60) = 60
```

Even though the general content and most property cards are fine, one or more hero images clearly depicting the wrong destination is enough to pull the final score down to reflect that problem.

The final score is therefore driven by the weakest relevant knowledge validation component, across whichever paths actually ran.

---

# 11. Issue Severity

The general knowledge score is also converted into issue severity:

| Score        | Severity |
| ------------ | -------- |
| Below 40     | High     |
| 40 to 69     | Medium   |
| 70 and above | Low      |

This severity is used when creating the general Knowledge Validation issue objects.

Property card geographic mismatches are always created as `High` severity issues, regardless of the general score.

Hero image geographic mismatches (`context_mismatch`) are also always created as `High` severity issues, using the title "Hero Image Context Mismatch." `uncertain` hero images never generate an issue at all — they are only logged.

---

# 12. Complete Example

Assume the user prompt is:

```text
Create a travel website for New York City.
```

The page contains:

```text
General content:
"New York City is located in the United States."
"Paris is one of the five boroughs of New York City."

Property cards:
1. Manhattan, New York
2. Flushing, NY
3. Jersey City, NJ
4. Brooklyn, NY

Hero images:
1. A skyline photo that is clearly NYC          -> valid
2. A generic tropical beach photo               -> uncertain
3. A cliffside Mediterranean villa overlooking
   turquoise water                              -> context_mismatch
```

## General Knowledge Validation

```text
User Prompt + Page Title
        |
        v
Tavily Search
        |
        v
LLM validates webpage claims
```

The LLM should identify:

```text
Verified:
New York City is in the United States

Incorrect:
Paris is one of the five boroughs of New York City
```

Example score:

```text
General Score = 60
```

## Destination Resolution

```text
User Prompt:
"Create a travel website for New York City"

        |
        v

LLM extracts:
Destination = New York City
Country = United States
Country Code = US

        |
        v

Country identity resolution:
Tavily evidence + LLM

        |
        v

Canonical result:
New York City, United States, US
```

This resolved destination is reused as-is for both Property Card Validation and Hero Image Validation.

## Property Cards

```text
Manhattan
    |
    -> Same city context
    -> valid

Flushing
    |
    -> Not safely resolved by deterministic checks
    -> ambiguous
    -> ThreadPool task
    -> Tavily geographic evidence
    -> LLM confirms it is within NYC
    -> valid

Jersey City
    |
    -> Country differs from destination
       if country codes are available
    OR
    -> ambiguous
    -> ThreadPool task
    -> LLM confirms it is an independent municipality
    -> context_mismatch

Brooklyn
    |
    -> ambiguous if not deterministically matched
    -> ThreadPool task
    -> Tavily + LLM
    -> valid
```

Result:

```text
Total Cards = 4
Valid Cards = 3

Card Score:
(3 / 4) × 100 = 75
```

## Hero Images

```text
Image 1 (NYC skyline)
    -> Gemini: valid

Image 2 (generic tropical beach)
    -> Gemini: uncertain
    -> logged, does not affect score

Image 3 (Mediterranean cliffside villa)
    -> Gemini: context_mismatch
    -> Issue: "Hero Image Context Mismatch" (High)
    -> Recommendation: "Review Hero Image"
```

Result:

```text
Total Images = 3
Mismatched = 1

Image Score:
round((3 - 1) / 3 × 100) = 67
```

## Final Score

```text
General Score = 60
Card Score = 75
Image Score = 67

Final Score:
min(60, 75, 67) = 60
```

The final Knowledge Validation result contains:

* Final score
* Verified claims
* Unsupported claims
* Uncertain claims
* General knowledge issues
* Property card context mismatch issues
* Hero image context mismatch issues
* Recommendations for fixing the problems

---

# Key Design Decisions

* The **user prompt is the source of truth** for destination intent, for text content, property cards, and hero images alike.
* Tavily provides external evidence. It does not directly make the validation decision.
* The primary LLM makes structured decisions using the webpage context and available Tavily evidence.
* Hero images are validated with a **separate multimodal call to Gemini**, since judging an image's content requires a model that can actually see it — text-based evidence alone can't validate a photo.
* Hero Image Validation and Property Card Validation share the same destination resolver, so the two paths never disagree about what "the destination" means.
* Country identity is dynamically resolved rather than relying on a fixed hardcoded list of country aliases.
* Deterministic checks are performed before expensive external validation for property cards.
* Only ambiguous property cards go through Tavily and LLM validation.
* Ambiguous cards are processed concurrently using `ThreadPoolExecutor` (default `max_workers=4`); hero images, by contrast, are sent to Gemini in a single batched call rather than per-image threads.
* Country mismatches can be rejected before city-level LLM validation.
* Metropolitan proximity does not automatically mean a property belongs to the destination.
* Property titles are deliberately excluded from geographic search evidence because marketing wording can be misleading.
* `uncertain` hero images are reported for visibility but never lower the score — only confirmed `context_mismatch` results do, mirroring how `uncertain` claims work in general knowledge validation.
* Hero image validation fails safe: a missing Gemini client, no hero images, an unresolved destination, a failed download, or a failed Gemini call all skip the path with a neutral score of `100` rather than penalizing the page for an infrastructure problem.
* The property card score is based on the percentage of valid cards; the hero image score is based on the percentage of non-mismatched images.
* The final Knowledge Validation score is the **minimum** across every path that actually ran (general is always included; property card and hero image scores are included only when that content exists).
* If there are no property cards and no hero images, the general knowledge score becomes the final score.

This approach keeps simple cases fast, uses external evidence for uncertain geography, reserves parallel LLM validation for cases where deterministic logic alone cannot make a reliable decision, and reserves the more expensive multimodal call for the one thing only a vision-capable model can judge — what the hero images actually show.