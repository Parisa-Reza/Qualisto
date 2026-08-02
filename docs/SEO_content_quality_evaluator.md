# SEO Quality Evaluator — Documentation

Rule-based evaluator that scores a webpage's on-page SEO quality. Starts at a
base score of **100** and deducts penalties for each issue found.

## Scoring Model

* **High severity** → `-15` points
* **Medium severity** → `-8` points
* **Low severity** → `-3` points
* Final score is floored at **0** (never negative)

---

## Checks Performed

### 1. Title Check (`_check_title`)

Evaluates the `<title>` tag length.

* **Missing** → title is empty/blank

  * Issue: `Missing SEO Title`
  * Severity: **High**
* **Too Short** → title length `< 30` characters

  * Issue: `Title Too Short`
  * Severity: **Medium**
* **Too Long** → title length `> 60` characters

  * Issue: `Title Too Long`
  * Severity: **Medium**
* **Valid range:** `30–60` characters → no issue

---

### 2. Meta Description Check (`_check_meta_description`)

Evaluates the meta description length.

* **Missing** → meta description is empty/blank

  * Issue: `Missing Meta Description`
  * Severity: **High**
* **Too Short** → length `< 120` characters

  * Issue: `Meta Description Too Short`
  * Severity: **Medium**
* **Too Long** → length `> 160` characters

  * Issue: `Meta Description Too Long`
  * Severity: **Medium**
* **Valid range:** `120–160` characters → no issue

---

### 3. Content Length Check (`_check_content_length`)

Evaluates total word count of `plain_text`.

* **Thin Content** → `< 300` words

  * Severity: **High**
* **Low Content Coverage** → `300–599` words

  * Severity: **Medium**
* **Good range** → `600–2500` words

  * No issue
* **Very Long Content** → `2501–4000` words

  * Severity: **Low**
* **Excessively Long Content** → `> 4000` words

  * Severity: **Medium**

---

### 4. Paragraph Length Check (`_check_paragraph_length`)

Evaluates each individual paragraph in `content.paragraphs`.

* Counts paragraphs where word count `> 180` words
* If **one or more** long paragraphs found:

  * Issue: `Long Paragraphs`
  * Severity: **Low**
  * Description reports how many paragraphs exceeded the limit

---

### 5. Internal Link Distribution (`_check_internal_link_distribution`)

Evaluates ratio of internal links (`href` starting with `/`) to word count.

* **Expected internal links** = `max(1, word_count // 500)`

  * i.e., at least 1 internal link expected per ~500 words
* If actual internal link count `< expected`:

  * Issue: `Low Internal Linking`
  * Severity: **Low**

---

### 6. External Link Distribution (`_check_external_link_distribution`)

Evaluates count of external links (`href` starting with `http`).

* **Too Many External Links** → `> 25` external links

  * Severity: **Low**
* No lower-bound check (having zero external links is fine)

---

### 7. Image-to-Content Ratio (`_check_image_content_ratio`)

Evaluates image count relative to word count.

* **Expected images** = `max(1, word_count // 800)`

  * i.e., at least 1 image expected per ~800 words
* If actual image count `< expected`:

  * Issue: `Low Image Coverage`
  * Severity: **Low**

---

### 8. Duplicate Headings (`_check_duplicate_headings`)

Checks all headings (`h1`–`h6` combined) for duplicate text.

* If any heading string appears **more than once** across all levels:

  * Issue: `Duplicate Headings`
  * Severity: **Low**
* Only reports **one** issue total, regardless of how many duplicates exist

---

### 9. Generic Headings (`_check_generic_headings`)

Checks all headings (`h1`–`h6` combined) against a blocklist of generic terms.

**Blocklisted terms** (case-insensitive, exact match after stripping):

* `home`

* `about`

* `page`

* `section`

* `article`

* `content`

* `welcome`

* `services`

* If any heading matches a blocklisted term:

  * Issue: `Generic Headings`
  * Severity: **Low**
  * Description lists the specific generic headings found

---

### 10. Readability Check (`_check_readability`)

Estimates average sentence length (a simplified readability proxy).

* Splits `plain_text` into sentences using `.`, `!`, `?` as delimiters
* Calculates: `avg = total_word_count / total_sentence_count`
* If `avg > 25` words per sentence:

  * Issue: `Low Readability`
  * Severity: **Low**
* If there are no sentences at all, check is skipped (no issue raised)

---

### 11. Keyword Relevance, Placement, and Density

The SEO evaluator checks whether important keywords derived from the
**user prompt** are represented appropriately in the webpage.

Keywords are expected to represent the topic the webpage was requested to
cover.

#### Keyword Sources

The evaluator can receive keywords in two ways:

1. **User prompt**

   * The evaluator extracts relevant keyword candidates from the user's prompt.
   * Example:

```text
User prompt:
"Create a travel webpage about Bali beaches and Bali hotels."
```

Possible extracted keywords include:

```text
bali
bali beaches
bali hotels
```

2. **Explicit target keywords**

   * The evaluator can also receive `target_keywords` directly.
   * This is useful when the application already has a known keyword list.

The evaluator should prefer the explicitly supplied keywords when available,
and otherwise derive keyword candidates from the user prompt.

---

#### Keyword Placement

After obtaining the target keywords, the evaluator checks whether they appear
in important SEO locations:

* Page title
* Meta description
* H1 headings
* H2 headings
* H3 headings
* Main page content

A keyword appearing only in the body but not in important metadata or headings
may receive a `Weak Keyword Placement` issue.

The purpose is to determine whether the webpage's SEO elements reflect the
topic requested by the user.

---

#### Missing Target Keyword

If an important target keyword does not appear anywhere in the relevant
webpage content, the evaluator reports:

```text
Missing Target Keyword
```

The issue indicates that the webpage may not adequately reflect the requested
topic.

---

#### Keyword Density

For each target keyword, the evaluator calculates:

```text
keyword density =
(keyword occurrences / total word count) × 100
```

Keyword matching is **case-insensitive**.

For example:

```text
Bali
bali
BALI
```

are treated as the same keyword.

The evaluator also supports multi-word keywords such as:

```text
bali beaches
bali hotels
travel guide
```

---

#### Density Thresholds

The current implementation uses the following heuristic thresholds:

* **Below 0.5%**

  * Issue: `Low Keyword Density`
  * Severity: **Low**

* **0.5%–2.0%**

  * No density issue

* **Above 2.0%**

  * Issue: `High Keyword Density`
  * Severity: **Medium**

These thresholds are **heuristic SEO evaluation thresholds**, not direct
Google ranking rules.

The evaluator should therefore treat keyword density as one signal among
multiple SEO-quality signals rather than assuming that a particular density
guarantees better Google rankings.

---

#### Keyword Density Example

Suppose the page contains approximately 300 words and the target keyword
appears 3 times:

```text
3 / 300 × 100 = 1%
```

The density is within the acceptable range:

```text
0.5% ≤ 1% ≤ 2.0%
```

Therefore, no keyword-density issue is generated.

If the keyword appears 15 times:

```text
15 / 300 × 100 = 5%
```

The density exceeds the current threshold:

```text
5% > 2.0%
```

Therefore:

```text
High Keyword Density
```

is generated.

---

#### Important Architectural Point

Keyword density should **not be evaluated independently of keyword relevance**.

The intended flow is:

```text
User Prompt
     ↓
Keyword Extraction
     ↓
Target Keywords
     ↓
┌─────────────────────────────────────┐
│        Webpage Evaluation           │
│                                     │
│ Title                               │
│ Meta Description                    │
│ H1 / H2 / H3                        │
│ Paragraphs / Main Content           │
│                                     │
│ → Keyword Presence                  │
│ → Keyword Placement                 │
│ → Keyword Density                   │
└─────────────────────────────────────┘
     ↓
SEO Quality Issues
     ↓
SEO Quality Score
```

This means the system is checking:

> **"Does the webpage use the important terms associated with what the user
> asked for, and are those terms used naturally?"**

It is not simply checking whether a webpage contains a large number of
repeated words.

---





### Notes

* Keyword extraction from the user prompt determines what the webpage is
  expected to discuss.
* The webpage itself is then checked against those target keywords.
* Title, meta description, H1, H2, H3, and body content are relevant keyword
  locations.
* Keyword matching is case-insensitive.
* Multi-word keywords are supported.
* Keyword density is calculated from the webpage's total word count.
* Keyword density thresholds are heuristic thresholds, not official Google
  ranking requirements.
* Keyword density alone should never determine whether content is
  SEO-friendly.

---

## Summary Table

| Check                            | Issue Title                | Severity | Threshold / Condition             |
| -------------------------------- | -------------------------- | -------- | --------------------------------- |
| Title                            | Missing SEO Title          | High     | title is empty                    |
| Title                            | Title Too Short            | Medium   | `< 30` chars                      |
| Title                            | Title Too Long             | Medium   | `> 60` chars                      |
| Meta Description                 | Missing Meta Description   | High     | description is empty              |
| Meta Description                 | Meta Description Too Short | Medium   | `< 120` chars                     |
| Meta Description                 | Meta Description Too Long  | Medium   | `> 160` chars                     |
| Content Length                   | Thin Content               | High     | `< 300` words                     |
| Content Length                   | Low Content Coverage       | Medium   | `300–599` words                   |
| Content Length                   | Very Long Content          | Low      | `2501–4000` words                 |
| Content Length                   | Excessively Long Content   | Medium   | `> 4000` words                    |
| Paragraph Length                 | Long Paragraphs            | Low      | any paragraph `> 180` words       |
| Internal Links                   | Low Internal Linking       | Low      | fewer than `1 per 500 words`      |
| External Links                   | Too Many External Links    | Low      | `> 25` external links             |
| Images                           | Low Image Coverage         | Low      | fewer than `1 per 800 words`      |
| Headings                         | Duplicate Headings         | Low      | any heading repeated across h1–h6 |
| Headings                         | Generic Headings           | Low      | heading matches blocklist term    |
| Readability                      | Low Readability            | Low      | avg sentence length `> 25` words  |
| Keyword presence  | `Missing Target Keyword` | Medium   | Target keyword does not appear in relevant page content |
| Keyword placement | `Weak Keyword Placement` | Low      | Keyword appears in body but not important SEO locations |
| Keyword density   | `Low Keyword Density`    | Low      | Density `< 0.5%`                                        |
| Keyword density   | No issue                 | —        | Density `0.5%–2.0%`                                     |
| Keyword density   | `High Keyword Density`   | Medium   | Density `> 2.0%`                                        |


---

## Notes / Potential Improvements

* **Internal link detection** (`href.startswith("/")`) assumes relative URLs
  only — it would miss internal links written as full absolute URLs
  (e.g., `https://samesite.com/about`).
* **External link detection** (`href.startswith("http")`) would also catch
  absolute internal links (e.g., `https://samesite.com/about`), incorrectly
  counting them as external.

