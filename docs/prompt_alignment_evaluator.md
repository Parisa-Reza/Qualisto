# Prompt Alignment Evaluator

The `PromptAlignmentEvaluator` asks an LLM to judge whether a generated webpage actually satisfies the original user request. It focuses purely on **content relevance**, not technical quality.

## What It Checks

| Area | Description |
|---|---|
| Destination and topic match | Does the page match the location or subject the user asked for? |
| Requested sections | Are the sections or information the user asked for actually present? |
| Missing requirements | Are any important parts of the request left out? |
| Off-topic content | Are there sections clearly unrelated to the requested destination or topic? |
| Contradictions | Does anything on the page conflict with what was requested? |

Every issue the LLM reports must point to *where* on the page the problem occurs (for example, "Under the Restaurants section..."), and every recommendation must say what to change, where to change it, and what it should be replaced with. Vague or generic complaints are not allowed by the prompt design.

## What It Does Not Check

This evaluator is scoped to alignment only. It is explicitly told to ignore:

- SEO and meta tags
- HTML structure
- Keyword density
- Image ALT text
- Links
- Factual correctness
- Writing quality

Those areas are handled by the other evaluators.

## Scoring

The LLM returns a score from 0 to 100 based on how well the page matches the request.

| Score | Meaning |
|---|---|
| 100 | Fully follows the request |
| 80–99 | Mostly aligned, only minor omissions |
| 60–79 | Partially aligned, some important requirements missing |
| 40–59 | Several requirements missing or noticeable off-topic content |
| 0–39 | Fails to follow the request |

If there are no real alignment problems, the LLM is instructed to return an empty issues list.

## Issue Severity

Unlike the score itself, which comes straight from the LLM, issue severity is decided afterward based on that score:

| Score range | Severity assigned to every issue |
|---|---|
| Below 40 | High |
| 40 to 69 | Medium |
| 70 and above | Low |

So all issues from a single evaluation share the same severity, since it is derived from the overall score rather than judged per issue.

## Output

The result includes:

- **score** — overall alignment score from 0 to 100
- **missing_requirements** — requirements from the prompt that were not addressed
- **off_topic_sections** — content found that does not match the request
- **issues** — turned into `Issue` objects, all sharing the severity determined by the score
- **recommendations** — turned into `Recommendation` objects, one per suggestion