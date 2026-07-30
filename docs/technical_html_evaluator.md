# Technical HTML Evaluator

The **Technical HTML Evaluator** checks the structural and technical health of a webpage using rule-based validation.

## Current Checks

-  HTML title exists
-  Meta description exists
-  Only one H1 heading is present
-  Empty anchor (`<a>`) tags
-  Missing `href` attribute in anchor tags
-  Missing image ALT attributes
-  Missing image `src` attributes
-  Invalid heading hierarchy (e.g., H1 → H4)
-  Duplicate HTML `id` attributes
-  Basic HTML structure validation
  - `<html>` tag
  - `<head>` tag
  - `<body>` tag
-  Broken hyperlinks (HTTP status validation)
-  Broken image URLs (HTTP status validation)

## Output

The evaluator returns:

- Technical HTML Score
- List of detected issues
- Improvement recommendations