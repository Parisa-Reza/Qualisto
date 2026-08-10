# Search Quality Evaluator

## Purpose

The Search Quality evaluator checks whether a webpage is useful and satisfying for a visitor who arrives from a search engine. It focuses on **content quality from the searcher's perspective**, not Google's actual ranking algorithm.

## What It Checks

The LLM rates each of these on a scale of 0 to 100 and returns them all alongside the overall score:

| Signal | What it's measuring |
|---|---|
| Helpfulness | Does the page give genuinely useful information, not just filler? |
| Completeness | Does it cover what a visitor reasonably needs to know? |
| Natural writing | Does it read naturally, the way a human would write it? |
| Repetition | Does it avoid saying the same thing over and over? |
| AI-sounding content | Does it avoid feeling generic or obviously machine-written? |
| Content depth | Does it go into real detail instead of staying shallow? |
| Readability | Is it easy to scan and understand? |
| User satisfaction | Would a visitor likely feel their search was answered? |

Along with these scores, the LLM also identifies the visitor's likely search intent, any useful sections that seem to be missing, concrete issues, and matching recommendations.

Every issue is required to say where on the page the problem is, and every recommendation has to say what to change and what should replace it. Vague comments like "the content could be improved" are explicitly disallowed by the prompt.

## Scoring

The overall score, from 0 to 100, comes directly from the LLM's judgment of the page. It is not calculated by averaging the individual signal scores above, those are returned separately for visibility, but the final score is the LLM's own holistic rating.

| Score | Meaning |
|---|---|
| 90–100 | Excellent |
| 80–89 | Very good |
| 70–79 | Good |
| 60–69 | Acceptable |
| 40–59 | Poor |
| 0–39 | Very poor |

The prompt specifically tells the LLM not to lower the score just because the page was AI generated, it should judge the actual content.

## Issue Severity

Severity is not decided by the LLM. It is worked out afterward in code, based on the overall score, and applied the same way to every issue from that evaluation:

| Score range | Severity |
|---|---|
| Below 40 | High |
| 40 to 69 | Medium |
| 70 and above | Low |

## What It Does Not Check

This evaluator is scoped to content and search experience only. It is explicitly told to ignore:

- HTML and technical SEO
- Keyword density and placement
- Backlinks and domain authority
- Core Web Vitals
- Schema markup
- Image ALT text
- Factual correctness and property card accuracy

Those areas belong to the other evaluators in the pipeline.

## Output

The result includes the overall score, the search intent summary, all nine individual signal scores, the list of missing sections, and the issues and recommendations converted into `Issue` and `Recommendation` objects.