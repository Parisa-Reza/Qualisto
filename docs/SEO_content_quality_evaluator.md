# SEO Quality Evaluator — Documentation

Rule-based evaluator that scores a webpage's on-page SEO quality. Starts at a
base score of **100** and deducts penalties for each issue found.

## Scoring Model

- **High severity** → `-15` points
- **Medium severity** → `-8` points
- **Low severity** → `-3` points
- Final score is floored at **0** (never negative)

---

## Checks Performed

### 1. Title Check (`_check_title`)
Evaluates the `<title>` tag length.

- **Missing** → title is empty/blank
  - Issue: `Missing SEO Title`
  - Severity: **High**
- **Too Short** → title length `< 30` characters
  - Issue: `Title Too Short`
  - Severity: **Medium**
- **Too Long** → title length `> 60` characters
  - Issue: `Title Too Long`
  - Severity: **Medium**
- **Valid range:** `30–60` characters → no issue

---

### 2. Meta Description Check (`_check_meta_description`)
Evaluates the meta description length.

- **Missing** → meta description is empty/blank
  - Issue: `Missing Meta Description`
  - Severity: **High**
- **Too Short** → length `< 120` characters
  - Issue: `Meta Description Too Short`
  - Severity: **Medium**
- **Too Long** → length `> 160` characters
  - Issue: `Meta Description Too Long`
  - Severity: **Medium**
- **Valid range:** `120–160` characters → no issue

---

### 3. Content Length Check (`_check_content_length`)
Evaluates total word count of `plain_text`.

- **Thin Content** → `< 300` words
  - Severity: **High**
- **Low Content Coverage** → `300–599` words
  - Severity: **Medium**
- **Good range** → `600–2500` words
  - No issue
- **Very Long Content** → `2501–4000` words
  - Severity: **Low**
- **Excessively Long Content** → `> 4000` words
  - Severity: **Medium**

---

### 4. Paragraph Length Check (`_check_paragraph_length`)
Evaluates each individual paragraph in `content.paragraphs`.

- Counts paragraphs where word count `> 180` words
- If **one or more** long paragraphs found:
  - Issue: `Long Paragraphs`
  - Severity: **Low**
  - Description reports how many paragraphs exceeded the limit

---

### 5. Internal Link Distribution (`_check_internal_link_distribution`)
Evaluates ratio of internal links (`href` starting with `/`) to word count.

- **Expected internal links** = `max(1, word_count // 500)`
  - i.e., at least 1 internal link expected per ~500 words
- If actual internal link count `< expected`:
  - Issue: `Low Internal Linking`
  - Severity: **Low**

---

### 6. External Link Distribution (`_check_external_link_distribution`)
Evaluates count of external links (`href` starting with `http`).

- **Too Many External Links** → `> 25` external links
  - Severity: **Low**
- No lower-bound check (having zero external links is fine)

---

### 7. Image-to-Content Ratio (`_check_image_content_ratio`)
Evaluates image count relative to word count.

- **Expected images** = `max(1, word_count // 800)`
  - i.e., at least 1 image expected per ~800 words
- If actual image count `< expected`:
  - Issue: `Low Image Coverage`
  - Severity: **Low**

---

### 8. Duplicate Headings (`_check_duplicate_headings`)
Checks all headings (`h1`–`h6` combined) for duplicate text.

- If any heading string appears **more than once** across all levels:
  - Issue: `Duplicate Headings`
  - Severity: **Low**
- Only reports **one** issue total, regardless of how many duplicates exist

---

### 9. Generic Headings (`_check_generic_headings`)
Checks all headings (`h1`–`h6` combined) against a blocklist of generic terms.

**Blocklisted terms** (case-insensitive, exact match after stripping):
- `home`
- `about`
- `page`
- `section`
- `article`
- `content`
- `welcome`
- `services`

- If any heading matches a blocklisted term:
  - Issue: `Generic Headings`
  - Severity: **Low**
  - Description lists the specific generic headings found

---

### 10. Readability Check (`_check_readability`)
Estimates average sentence length (a simplified readability proxy).

- Splits `plain_text` into sentences using `.`, `!`, `?` as delimiters
- Calculates: `avg = total_word_count / total_sentence_count`
- If `avg > 25` words per sentence:
  - Issue: `Low Readability`
  - Severity: **Low**
- If there are no sentences at all, check is skipped (no issue raised)

---

## Summary Table

| Check | Issue Title | Severity | Threshold / Condition |
|---|---|---|---|
| Title | Missing SEO Title | High | title is empty |
| Title | Title Too Short | Medium | `< 30` chars |
| Title | Title Too Long | Medium | `> 60` chars |
| Meta Description | Missing Meta Description | High | description is empty |
| Meta Description | Meta Description Too Short | Medium | `< 120` chars |
| Meta Description | Meta Description Too Long | Medium | `> 160` chars |
| Content Length | Thin Content | High | `< 300` words |
| Content Length | Low Content Coverage | Medium | `300–599` words |
| Content Length | Very Long Content | Low | `2501–4000` words |
| Content Length | Excessively Long Content | Medium | `> 4000` words |
| Paragraph Length | Long Paragraphs | Low | any paragraph `> 180` words |
| Internal Links | Low Internal Linking | Low | fewer than `1 per 500 words` |
| External Links | Too Many External Links | Low | `> 25` external links |
| Images | Low Image Coverage | Low | fewer than `1 per 800 words` |
| Headings | Duplicate Headings | Low | any heading repeated across h1–h6 |
| Headings | Generic Headings | Low | heading matches blocklist term |
| Readability | Low Readability | Low | avg sentence length `> 25` words |

---

## Notes / Potential Improvements

- **Internal link detection** (`href.startswith("/")`) assumes relative URLs
  only — it would miss internal links written as full absolute URLs
  (e.g., `https://samesite.com/about`).
- **External link detection** (`href.startswith("http")`) would also catch
  absolute internal links (e.g., `https://samesite.com/about`), incorrectly
  counting them as external.
