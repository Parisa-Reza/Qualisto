# Technical HTML Evaluator

The Technical HTML Evaluator looks at a webpage's HTML and checks it for common technical problems. It groups its checks into six categories, and each category affects the score on its own.

## What It Checks

### 1. Structure
- The page has the basic `<html>`, `<head>`, and `<body>` tags
- The page only has one `<h1>`. If there are more, each extra one is flagged
- Headings go in order and don't skip levels, like jumping from an H1 straight to an H3 with no H2 in between
- HTML `id` attributes are unique. If the same id shows up more than once, each duplicate is flagged

### 2. Metadata
- There's a `<title>` tag
- There's a meta description

### 3. Links
- Every link has a real `href` attribute
- Links actually work and don't return an error when checked live (see the Optimization section below)

### 4. Images
- Every image has a `src` attribute
- Images actually load and don't return an error when checked live

Whether an image has alt text is checked separately, under Accessibility, so it's not counted twice.

### 5. Accessibility
- Images have an `alt` attribute at all
- Links have some way for a screen reader to describe them. This can come from visible text, an aria-label, the alt text of an image inside the link, or a title attribute, checked in that order. So a link that's just an image with good alt text still counts as fine
- The `<html>` tag has a `lang` attribute so screen readers and browsers know what language the page is in

### 6. HTML Validation
- The page has a viewport meta tag, so it displays properly on phones instead of shrinking down a desktop layout
- The page declares a character encoding, so text and special characters render correctly

## How Scoring Works

Scoring starts at 100 points. Instead of subtracting points for every single issue found, the evaluator subtracts points once per category.

Each category has its own fixed penalty:

| Category | Penalty |
|---|---|
| Structure | 20 |
| Metadata | 15 |
| Links | 25 |
| Images | 20 |
| Accessibility | 10 |
| HTML | 10 |

If a category has at least one issue, its full penalty is taken off the score one time, no matter how many issues were found in that category. So a page with one broken link loses the same 25 points as a page with fifty broken links. A category with no issues doesn't cost anything.

The final score can never drop below 0.

This is done on purpose. It stops one really messy category, like a page full of broken links, from wiping out the whole score by itself, while still making sure every category with a real problem gets penalized.

## Optimization

Checking whether links and images actually work means making a live request to each URL. Since these requests mostly involve waiting on a response rather than doing heavy computation, the evaluator checks them at the same time instead of one after another, using a thread pool of up to 10 workers at once. Each check times out after 5 seconds so one slow or broken URL can't hold up the whole evaluation. It also tries a lightweight HEAD request first, and falls back to a GET request if the server doesn't support HEAD. This means a page with dozens or hundreds of links and images gets checked much faster than doing it one at a time.

## Output

The evaluator returns:

- A technical HTML score from 0 to 100
- A list of issues found, each with a severity, a title, and details on what's wrong and where
- A matching list of recommendations, one for each issue, explaining how to fix it