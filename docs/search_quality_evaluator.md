# Search Quality Module

## Purpose

The Search Quality module checks whether a webpage is useful and satisfying for a user who arrives from a search engine.

It focuses on **content quality from the searcher's perspective**, not Google's actual ranking algorithm.

---

## Checks

The LLM evaluates these criteria, each from **0–100**:

1. **Search Intent** — Does the page satisfy what the user is likely searching for?
2. **Helpfulness** — Does it provide genuinely useful information?
3. **Completeness** — Does it cover the important information users expect?
4. **Natural Writing** — Does it read naturally for humans?
5. **Repetition** — Does it avoid unnecessary repetition?
6. **AI-Sounding Content** — Does it avoid generic or obviously machine-generated writing?
7. **Content Depth** — Does it provide meaningful detail rather than shallow information?
8. **Readability** — Is it easy to read and scan?
9. **User Satisfaction** — Is the visitor likely to feel their information need was satisfied?

The LLM also identifies:

* Missing sections
* Issues
* Recommendations

---

## Flow

```text
WebsiteContent
      │
      ▼
SearchQualityEvaluator
      │
      ▼
Build Search Quality Prompt
      │
      ▼
LLM
      │
      ▼
Structured SearchQualityLLMResult
      │
      ├── Search Intent Score
      ├── Helpfulness Score
      ├── Completeness Score
      ├── Natural Writing Score
      ├── Repetition Score
      ├── AI-Sounding Score
      ├── Content Depth Score
      ├── Readability Score
      └── User Satisfaction Score
      │
      ▼
Python scoring
      │
      ▼
Search Quality Score /100
      │
      ├── Issues
      ├── Recommendations
      └── Missing Sections
      │
      ▼
SearchQualityResult
```

## Coordination

```text
Extractor
   │
   │ WebsiteContent
   ▼
Search Quality Evaluator
   │
   │ sends page context
   ▼
LLM
   │
   │ structured evaluation
   ▼
Search Quality Result
   │
   ▼
Overall Evaluation Pipeline
```

### Important

This module does **not** check:

* Factual correctness
* Property-card correctness
* Technical SEO
* Backlinks
* Keyword density
* Google's exact ranking algorithm

Those responsibilities belong to other parts of the evaluation system.
