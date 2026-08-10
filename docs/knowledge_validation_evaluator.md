# Knowledge Validation Module

---

# 1. Purpose

The **Knowledge Validation** module verifies whether the factual information generated on a travel webpage is accurate and contextually correct.

It focuses only on:

- Factual correctness
- Destination correctness
- Property card relevance

It **does not evaluate**:

- SEO
- Readability
- HTML quality
- Keyword density
- Writing style

---

# 2. Overall Workflow

```text
                    WebsiteContent
                          │
                          ▼
             KnowledgeValidationEvaluator
                          │
          ┌───────────────┴────────────────┐
          │                                │
          ▼                                ▼
 General Knowledge Validation      Property Card Validation
          │                                │
          ▼                                ▼
 Collect Search Evidence           Validate Cards Concurrently
      (Tavily Search)                (ThreadPoolExecutor)
          │                                │
          ▼                                ▼
      Gemini LLM                  Multiple Gemini Calls
          │                                │
          └───────────────┬────────────────┘
                          ▼
            Merge Results & Apply Penalties
                          │
                          ▼
           KnowledgeValidationResult
```

---

# 3. General Knowledge Validation Flow

The webpage content is validated as a whole before individual property cards are checked.

Flow:

```text
WebsiteContent
      │
      ▼
Build Search Query
      │
      ▼
Tavily Search
      │
      ▼
External Search Evidence
      │
      ▼
Prompt Builder
      │
      ▼
Gemini LLM
      │
      ▼
KnowledgeValidationLLMResult
```
1. One Tavily search
- Query built from the page title + H1 + H2 + H3.
- Returns up to 5 search results.
2. One Gemini call 
**Receives**
- Webpage content
- Tavily search evidence
- Instructions (your prompt)
**Returns:**
- Score
- Verified claims
- Unsupported claims
- Uncertain claims
- Issues
- Recommendations
---

# 4. How Tavily and Gemini Work Together

The module combines **retrieval** and **reasoning**.

## Step 1 — Build Search Query

A search query is generated from the webpage.

Example

```text
Page Title:
Things to Do in London

H1:
London Travel Guide

H2:
Best Attractions

H2:
Hotels in London
```

Generated query

```text
Things to Do in London
London Travel Guide
Best Attractions
Hotels in London
```

---

## Step 2 — Tavily Search

The query is sent to Tavily.

Example request

```text
Things to Do in London
London Travel Guide
Best Attractions
Hotels in London
```

Example response

```text
Result 1

Title:
Visit London

URL:
https://visitlondon.com

Snippet:
London is the capital of England.
Popular attractions include Tower Bridge,
Buckingham Palace and the London Eye.


Result 2

Title:
Britannica

URL:
https://britannica.com

Snippet:
London is one of the world's largest cities
and is located in southeastern England.
```

The evaluator converts these results into a readable text block called:

```text
search_evidence
```

---

## Step 3 — Build the Prompt

Gemini receives three things together:

```text
1. Webpage Content

2. External Search Evidence

3. Instructions describing what to verify
```

Example

```text
PAGE TITLE

Things to Do in London

WEBPAGE CONTENT

The Eiffel Tower is London's most famous attraction.

SEARCH EVIDENCE

Visit London

Tower Bridge
Buckingham Palace
London Eye

Britannica

London is the capital of England.
```

---

## Step 4 — Gemini Performs Reasoning

Gemini compares:

```text
Webpage

vs

External Search Evidence
```

It determines whether the webpage facts are:

- Verified
- Unsupported
- Uncertain

It also generates:

- Issues
- Recommendations
- Knowledge score

Example output

```text
Score:
82

Verified Claims

London is the capital of England.

Unsupported Claims

The Eiffel Tower is London's most famous attraction.

Issues

Incorrect attraction information.

Recommendation

Replace Eiffel Tower with a London attraction.
```

---

# 5. Property Card Validation

After the webpage content has been validated, every extracted property card is validated independently.

Each card receives its own Gemini request.

Flow

```text
Property Card
      │
      ▼
Build Search Query
      │
      ▼
Tavily Search
      │
      ▼
Search Evidence
      │
      ▼
Gemini
      │
      ▼
valid

or

context_mismatch
```

---

# 6. Property Card Example

Suppose the webpage is:

```text
London Travel Guide
```

Property Card

```text
Luxury Paris Hotel

City:
Paris

Country:
France
```

Generated Tavily query

```text
Luxury Paris Hotel
Paris
France
Hotel
```

Tavily returns

```text
Luxury Paris Hotel

Paris, France
```

Gemini now compares

```text
Page Destination

London

vs

Property Destination

Paris
```

Gemini returns

```text
status

context_mismatch

reason

The property belongs to Paris,
which does not match the webpage destination.
```

The evaluator converts this into:

```text
Issue

+

Recommendation
```

---

# 7. Concurrent Property Card Validation

Property cards are validated **concurrently** using:

```python
ThreadPoolExecutor
```

instead of validating them one by one.

Flow

```text
Property Cards

Card 1
Card 2
Card 3
Card 4
Card 5
...
Card N

        │
        ▼

ThreadPoolExecutor

        │
        ├───────────────┐
        │               │
        ▼               ▼

Worker 1          Worker 2

Gemini            Gemini

        │               │

        ▼               ▼

Worker 3          Worker 4

Gemini            Gemini

        │               │
        └───────┬───────┘
                ▼

Collect Results

                ▼

KnowledgeValidationResult
```

Each worker performs:

```text
Build Search Query

↓

Tavily Search

↓

Gemini Validation

↓

Return Result
```

independently.

---

# 8. Why Concurrency Improves Performance

Each property card requires:

- One Tavily request
- One Gemini request

Both operations spend most of their time waiting for remote servers to respond.

Instead of waiting for one card to finish before starting the next one, multiple cards are processed simultaneously.

---

# 9. Performance Comparison

Suppose:

- 20 property cards
- Each card takes approximately **10 seconds**
  (Tavily + Gemini)

## Without ThreadPoolExecutor

Cards are processed sequentially.

```text
Card 1

↓

Card 2

↓

Card 3

↓

...

↓

Card 20
```

Total execution time

```text
20 × 10

≈ 200 seconds
```

---

## With ThreadPoolExecutor

Suppose

```python
max_workers = 5
```

Five cards are processed simultaneously.

Execution happens in batches.

```text
Batch 1

Cards 1–5

↓

Batch 2

Cards 6–10

↓

Batch 3

Cards 11–15

↓

Batch 4

Cards 16–20
```

Each batch requires roughly

```text
10 seconds
```

Total execution time

```text
4 × 10

≈ 40 seconds
```

Performance improvement

```text
Without workers

≈ 200 seconds

With 5 workers

≈ 40 seconds

Around 80% reduction in execution time.
```

---

# 10. Issue Generation

Whenever Gemini returns

```text
context_mismatch
```

the evaluator creates

```text
Issue

+

Recommendation
```

Example

Issue

```text
Property Card Context Mismatch

The property card

"Luxury Paris Hotel"

belongs to Paris, France,
which does not match the webpage destination.
```

Recommendation

```text
Review the property card and
replace or remove it if it does not
belong to the webpage destination.
```

Each mismatched property card generates its own issue.

---

# 11. Final Score Calculation

The final knowledge validation score consists of two stages.

## Stage 1

Gemini evaluates the webpage content.

Example

```text
Knowledge Score

90
```

---

## Stage 2

Each mismatched property card reduces the score.

Current implementation

```python
final_score = max(
    0,
    gemini_score - (card_issues × 15)
)
```

Example

```text
Gemini Score

90

↓

2 Property Card Mismatches

↓

Penalty

2 × 15

↓

Final Score

60
```

The score is never allowed to become negative.

---

# 12. Final Output

The evaluator returns

```text
KnowledgeValidationResult

score

verified_claims

unsupported_claims

uncertain_claims

issues

recommendations
```

Example

```text
Knowledge Validation Score

78

Verified Claims

• London is the capital of England.

• Tower Bridge is located in London.

Unsupported Claims

• Eiffel Tower is London's most famous attraction.

Uncertain Claims

• London receives exactly 25 million tourists every year.

Issues

• Incorrect attraction information.

• Property Card Context Mismatch.

Recommendations

• Correct the unsupported factual claim.

• Replace or remove the incorrect property card.
```

---

# 13. Summary

The Knowledge Validation module:

- Extracts contextual information from the webpage.
- Uses Tavily Search to retrieve reliable external evidence.
- Passes both the webpage content and search evidence to Gemini.
- Gemini verifies factual claims using the supplied evidence.
- Every property card is validated independently.
- Property card validation runs concurrently using `ThreadPoolExecutor`.
- Concurrency significantly reduces total evaluation time when many property cards exist.
- The final result combines the LLM-generated knowledge score with penalties for property card mismatches to produce a single `KnowledgeValidationResult`.