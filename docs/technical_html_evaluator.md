# Technical HTML Evaluator

The **Technical HTML Evaluator** checks the structural and technical health of a webpage using rule-based validation. Checks are organized into categories, each contributing independently to the final score.

## What It Checks

Checks are grouped into six categories. Within a category, one or more individual checks run and each finding is reported as a separate issue.

### 1. Structure
- Required `<html>`, `<head>`, and `<body>` tags are present
- Only one `<h1>` exists on the page (additional H1s are flagged individually)
- Heading hierarchy does not skip levels (e.g. H1 → H3 without an H2 in between)
- HTML `id` attributes are unique (duplicate ids are flagged individually)

### 2. Metadata
- A `<title>` element exists
- A meta description exists

### 3. Links
- Anchor tags do not have empty visible text
- Anchor tags have a valid `href` attribute
- Linked URLs are reachable and do not return an HTTP error status (checked live, see [Optimization](#optimization))

### 4. Images
- Images have ALT text
- Images have a valid `src` attribute
- Image URLs are reachable and do not return an HTTP error status (checked live, see [Optimization](#optimization))

### 5. Accessibility
- Images include an `alt` attribute at all (distinct from the Images check above — this specifically flags images missing the attribute itself, not just missing text)

### 6. HTML Validation
- Anchor elements are complete (i.e. not missing `href`)

## Issue Location Reporting

Every issue includes precise, developer-readable context instead of an arbitrary index:

- **Location** — a short CSS-style breadcrumb anchored at the nearest ancestor element with an `id`, plus the source line number when available (e.g. `div#property-brand > a.responsive-image (line 2142)`)
- **HTML** — a truncated snippet of the actual element's outer HTML, so the exact tag can be found via search in the page source

This makes each issue directly traceable to a specific place in the page, rather than requiring the developer to guess from a generic counter.

## Scoring Mechanism

Scoring starts at **100** and is calculated **per category, not per issue**:

- Each of the six categories has a fixed penalty weight:

  | Category | Penalty |
  |---|---|
  | Structure | 20 |
  | Metadata | 15 |
  | Links | 25 |
  | Images | 20 |
  | Accessibility | 10 |
  | HTML | 10 |

- If a category has **one or more** issues, its full penalty is subtracted **once** — finding 1 broken link and finding 50 broken links both cost the same 25 points.
- Categories with no issues contribute no penalty.
- The final score is floored at **0** (never goes negative).

This category-level (rather than per-issue) deduction is intentional: it prevents a single problematic area — e.g. a page with dozens of broken links — from disproportionately destroying the overall score, while still ensuring every category with a real problem is penalized.

## Optimization

- **Concurrent link/image validation**: Checking whether every link and image URL is reachable requires a live HTTP request per URL. Since these requests are network-bound (the program mostly waits on a response rather than doing CPU work), link and image checks run concurrently using a `ThreadPoolExecutor` instead of sequentially.
- **`MAX_WORKERS = 10`**: Caps the number of concurrent HTTP requests in flight at once. The actual worker count used is `min(MAX_WORKERS, number_of_urls)`, so small pages don't spin up unnecessary threads.
- **`REQUEST_TIMEOUT = 5` seconds**: Each URL check times out after 5 seconds so a single slow/unresponsive URL can't stall the whole evaluation.
- **HEAD-first, GET-fallback**: Each URL is checked with a lightweight `HEAD` request first; if the server responds `403` or `405` (which some servers return for HEAD requests specifically), it retries with a streamed `GET` instead of failing outright.
- **Net effect**: for a page with dozens or hundreds of links/images, concurrent checking turns what would be a slow, one-request-at-a-time scan into requests running in parallel batches of up to 10 — substantially reducing total evaluation time without overwhelming the target server.

## Output

The evaluator returns:

- Technical HTML Score (0–100)
- List of detected issues, each with severity, title, and a description containing the summary, location, and HTML snippet
- A matching list of improvement recommendations, one per issue