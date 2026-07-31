
# Prompt alignment checks

The `PromptAlignmentEvaluator` asks an LLM to judge whether a generated webpage actually satisfies the original user request. It focuses purely on **content relevance**, not technical quality.

## What it checks

1. **Topic coverage** — are the topics the user asked for actually present on the page?
2. **Missing requirements** — are any important requirements from the request left out?
3. **Focus** — does the page stay on the requested subject, or does it drift?
4. **Off-topic content** — are there sections clearly unrelated to the request?
5. **Overall score** — a satisfaction score from 0–100 summarizing alignment.

## What it does NOT check

This evaluator explicitly ignores technical/SEO concerns, which are presumably handled by other evaluators:

- HTML structure
- Technical SEO
- Keyword density / placement
- Links
- Images
- ALT attributes
- Title length
- Meta description length

## Output

The result includes:
- `score` — overall alignment score (0–100)
- `missing_requirements` — list of requirements not addressed
- `off_topic_sections` — list of unrelated content found
- `issues` — converted into `Issue` objects (severity: Medium)
- `recommendations` — converted into `Recommendation` objects