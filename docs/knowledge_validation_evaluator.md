# Knowledge Validation Module

## Claims → factual correctness
```
Webpage text
   ↓
ClaimExtractor
   ↓
"The Eiffel Tower is in Paris."
   ↓
Tavily → finds web evidence
   ↓
Gemini → verifies the claim
   ↓
verified / unsupported / uncertain
```

## Cards → destination/context correctness

```
Webpage: New York City
   ↓
Property Card: Paris Hotel
   ↓
Gemini compares page context + card location
   ↓
valid / context_mismatch
```

***Claim = “Is this fact true?”*** <br>
***Card = “Does this property belong on this page?***

## 1. Purpose

The Knowledge Validation module checks whether factual information on a webpage is supported by external evidence.

For our travel website, it also checks whether **property cards belong to the webpage's destination**.

Example:

```text
Page: New York City Travel Guide

✓ Jersey City Apartment
✗ Paris Hotel
```

---

## 2. Main Flow

```text
Website
   │
   ▼
ContentExtractor
   │
   ▼
WebsiteContent
   │
   ├───────────────┐
   │               │
   ▼               ▼
Claims         Property Cards
   │               │
   ▼               ▼
ClaimExtractor   Card Validation
   │               │
   ▼               ▼
Tavily Search      │
   │               │
   ▼               │
Web Evidence       │
   │               │
   └───────┬───────┘
           ▼
         Gemini
           │
           ▼
   KnowledgeValidationResult
```

---

## 3. Factual Claim Validation

### Step 1 — Extract claims

`ClaimExtractor` extracts factual statements from the webpage.

Example:

```text
"Bali is an Indonesian island."
```

### Step 2 — Search the claim

`TavilySearchClient` searches the web for evidence.

```text
Claim
  ↓
Tavily
  ↓
Search Results
```

### Step 3 — Gemini evaluates the evidence

Gemini receives:

```text
CLAIM
+
WEB EVIDENCE
```

and returns:

```text
verified
unsupported
uncertain
```

### Step 4 — Create issues

```text
verified
    → no issue

unsupported
    → High severity issue

uncertain
    → Medium severity issue
```

---

## 4. Property Card Validation

Property cards are extracted into `WebsiteContent.property_cards`.

Example:

```text
Page:
New York City Travel Guide

Card:
Luxury Paris Hotel
Paris, France
```

The evaluator sends Gemini:

```text
Page title
+
Page headings
+
Page content context
+
Property card information
```

Gemini returns:

```text
valid
```

or:

```text
context_mismatch
```

Example:

```text
New York City page
        +
Jersey City property
        ↓
      valid
```

```text
New York City page
        +
Paris property
        ↓
context_mismatch
```

---

## 5. Coordination

The main coordinator is:

```text
evaluator/evaluators/knowledge_validation.py
```

`KnowledgeValidationEvaluator` coordinates:

```text
ClaimExtractor
      ↓
TavilySearchClient
      ↓
Gemini
      ↓
Claim result

Property Cards
      ↓
Gemini
      ↓
Card result
```

Finally, both results are combined into:

```text
KnowledgeValidationResult
```

---

## 6. Output

The module returns:

```text
score
issues
recommendations
verified_claims
unsupported_claims
uncertain_claims
```

Example:

```text
Knowledge Validation Score: 75

Issues:
- Unsupported Claim
- Property Card Context Mismatch

Recommendations:
- Verify the factual claim
- Review the property card
```

---


## 7. Important Boundary

Knowledge Validation checks **factual correctness and contextual correctness**.

It does **not** check:

* Keyword density
* SEO
* Readability
* Search intent
* AI-sounding writing
* HTML quality
