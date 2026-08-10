# SEO Quality Evaluator

This evaluator looks at a webpage and checks how well it follows common SEO best practices. It starts every page at a score of 100 and takes points away each time it finds a problem. The score never drops below 0.

## How Scoring Works

Every issue found has a severity level, and each severity costs a different number of points.

A High severity issue costs 15 points.
A Medium severity issue costs 8 points.
A Low severity issue costs 3 points.

Unlike the technical HTML evaluator, this one deducts points per individual issue rather than per category, so a page with many small problems can lose a lot of points even if each one is minor.

## What It Checks

### Title Length

The evaluator looks at how long the page title is.

If there is no title at all, that is a High severity issue called Missing SEO Title.

If the title is shorter than 30 characters, that is a Medium severity issue called Title Too Short.

If the title is longer than 60 characters, that is a Medium severity issue called Title Too Long.

A title between 30 and 60 characters is considered fine and raises no issue.

### Meta Description Length

The same idea applies to the meta description, just with different numbers.

If it is missing entirely, that is a High severity issue called Missing Meta Description.

If it is shorter than 120 characters, that is a Medium severity issue called Meta Description Too Short.

If it is longer than 160 characters, that is a Medium severity issue called Meta Description Too Long.

Anything between 120 and 160 characters is considered fine.

### Content Length

This check counts the total number of words on the page.

Fewer than 300 words is treated as Thin Content and is a High severity issue.

Between 300 and 599 words is Low Content Coverage, a Medium severity issue.

Between 600 and 2500 words is considered a healthy range and raises no issue.

Between 2501 and 4000 words is flagged as Very Long Content, a Low severity issue, mainly as a nudge to keep the content organized.

Anything above 4000 words is flagged as Excessively Long Content, a Medium severity issue, since very long pages can overwhelm readers.

### Paragraph Length

The evaluator looks at each paragraph individually and counts how many go over 180 words. If even one paragraph is that long, it raises a single Low severity issue called Long Paragraphs, and the description tells you how many paragraphs were too long.

### Internal Links

Internal links are links whose href starts with a forward slash, meaning they point somewhere else on the same site. The evaluator expects roughly one internal link for every 500 words of content, with at least one expected no matter how short the page is.

If the page has fewer internal links than expected, it raises a Low severity issue called Low Internal Linking.

Worth noting, this check only recognizes links written as relative paths like /about. A link written as a full URL to the same site, like https://yoursite.com/about, would not be counted as internal here.

### External Links

External links are links whose href starts with http. If a page has more than 25 of them, that is flagged as a Low severity issue called Too Many External Links. There is no lower limit, so having zero external links is perfectly fine.

Since this check simply looks for hrefs starting with http, a full URL pointing back to the same site would technically be counted as external too, even though it isn't really leaving the page.

### Images Versus Content

The evaluator expects roughly one image for every 800 words of content, again with at least one expected regardless of length. If the page has fewer images than that, it raises a Low severity issue called Low Image Coverage.

### Duplicate Headings

All headings from h1 through h6 are combined into one list. If any heading text shows up more than once anywhere in that combined list, the evaluator raises a single Low severity issue called Duplicate Headings. It does not list every duplicate individually, just flags that duplicates exist.

### Generic Headings

The evaluator also checks headings against a small list of overly generic words such as home, about, page, section, article, content, welcome, and services. If a heading matches one of these words exactly after removing extra spaces and ignoring capitalization, it is flagged. This raises a Low severity issue called Generic Headings, and the description lists exactly which generic headings were found.

### Readability

To estimate readability, the evaluator splits the page text into sentences using periods, exclamation points, and question marks as breakpoints. It then divides the total word count by the number of sentences to get an average sentence length.

If that average comes out above 25 words per sentence, it raises a Low severity issue called Low Readability. If the page has no sentences at all, this check is simply skipped.

### Keyword Coverage

This part works a bit differently from the others because it depends on what the user originally asked for when the page was generated.

The evaluator takes the original user prompt and sends it to the language model, asking it to pull out the important topics the page should cover. Things like destination names, attractions, accommodation types, or explicit phrases the prompt mentioned. Generic instruction words like create, generate, or optimize are filtered out on purpose so they don't get treated as topics. If the prompt is empty, or if the extraction call fails for any reason, the evaluator simply treats the page as having no target keywords and skips these checks quietly.

Once it has a list of keywords, up to 20 of them, it checks each one against the title, the meta description, the h1 headings, the h2 headings, the h3 headings, and the full body text.

If a keyword does not appear anywhere at all across any of those places, it goes into a Medium severity issue called Missing Target Topics, and the description lists every missing keyword together.

If a keyword only shows up in the body text but never in the title, meta description, or any heading, it is considered weakly placed. These go into a separate Low severity issue called Weak Keyword Placement.

### Keyword Density

For each keyword that does appear on the page, the evaluator also measures how often it shows up relative to the total word count, expressed as a percentage. This calculation is case insensitive and works for multi word phrases as well as single words.

If a keyword's density comes out below 0.5 percent, it is added to a Low severity issue called Low Target Keyword Coverage.

If a keyword's density comes out above 2 percent, it is added to a Medium severity issue called Potential Keyword Overuse.

Anything between those two numbers is considered a healthy, natural amount of usage and raises no issue.

As an example, if a page has 300 words total and a keyword appears 3 times, that works out to 1 percent density, which falls comfortably in the healthy range. If that same keyword appeared 15 times instead, the density would be 5 percent, which is well above the 2 percent threshold and would trigger the overuse issue.

These thresholds are simply heuristics built into this evaluator. They are not official Google ranking rules, and keyword density should be treated as just one small signal among many, not something to optimize for on its own.

## Summary Table

| Check | Issue Title | Severity | Condition |
|---|---|---|---|
| Title | Missing SEO Title | High | title is empty |
| Title | Title Too Short | Medium | fewer than 30 characters |
| Title | Title Too Long | Medium | more than 60 characters |
| Meta Description | Missing Meta Description | High | description is empty |
| Meta Description | Meta Description Too Short | Medium | fewer than 120 characters |
| Meta Description | Meta Description Too Long | Medium | more than 160 characters |
| Content Length | Thin Content | High | fewer than 300 words |
| Content Length | Low Content Coverage | Medium | 300 to 599 words |
| Content Length | Very Long Content | Low | 2501 to 4000 words |
| Content Length | Excessively Long Content | Medium | more than 4000 words |
| Paragraph Length | Long Paragraphs | Low | any paragraph over 180 words |
| Internal Links | Low Internal Linking | Low | fewer than about 1 per 500 words |
| External Links | Too Many External Links | Low | more than 25 external links |
| Images | Low Image Coverage | Low | fewer than about 1 per 800 words |
| Headings | Duplicate Headings | Low | any heading repeated across h1 to h6 |
| Headings | Generic Headings | Low | heading matches the blocklist |
| Readability | Low Readability | Low | average sentence length over 25 words |
| Keyword Presence | Missing Target Topics | Medium | keyword not found anywhere relevant |
| Keyword Placement | Weak Keyword Placement | Low | keyword only found in body text |
| Keyword Density | Low Target Keyword Coverage | Low | density below 0.5 percent |
| Keyword Density | Potential Keyword Overuse | Medium | density above 2 percent |

## Things Worth Knowing

The internal link check only recognizes links that start with a forward slash, so an internal link written as a full absolute URL to the same domain would be missed.

The external link check only looks for links starting with http, so an absolute link pointing back to the same site would be miscounted as external.

Keyword extraction depends entirely on the user prompt and the language model's interpretation of it. If the prompt is vague, empty, or the extraction call fails, the page simply won't be checked against any target topics, and no keyword related issues will appear.

Keyword density is only calculated for keywords that already appear on the page at least once. A keyword that is completely missing shows up under Missing Target Topics instead, not under a zero percent density issue.