import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import EvaluationResult, Issue, Recommendation

logger = logging.getLogger(__name__)


class TechnicalHTMLEvaluator:
    """
    Evaluates the technical HTML quality of a webpage.

    Every issue reports:
      - what is wrong (in plain language)
      - a stable, human-readable Location breadcrumb
      - a pastable CSS Selector a developer can drop straight into their own browser DevTools Console (document.querySelector(...)) to jump to the exact element on their machine, in Inspect
      - a truncated raw HTML snippet as a final sanity check

    Locations are anchored to STABLE attributes (id, data-id, data-property_id, data-testid) rather than volatile ones like a tracking-parameter-laden href, so the same Location/Selector still works even if the underlying href changes on every page load.

    Each check runs against exactly one category, and no two checks report the same underlying problem twice (e.g. a missing image ALT is only ever reported once, under "accessibility" - not once under "images" and again under "accessibility").
    """

    MAX_WORKERS = 10
    REQUEST_TIMEOUT = 5
    HEADERS = {"User-Agent": "Mozilla/5.0"}
    SNIPPET_LIMIT = 200

    # Attributes checked, in priority order, when anchoring a Location to something stable. The first one found walking UP the tree wins.
    STABLE_ATTRS = ("id", "data-id", "data-property_id", "data-testid")

    PENALTIES = {
        "structure": 20,
        "metadata": 15,
        "links": 25,
        "images": 20,
        "accessibility": 10,
        "html": 10,
    }

    @classmethod
    def evaluate(cls, content: WebsiteContent) -> EvaluationResult:
        logger.info("Technical HTML evaluation started | url=%s", content.url)

        issues = []
        recommendations = []
        categories = {}

        cls._run_check("structure", cls._check_structure, content, issues, recommendations, categories)
        cls._run_check("metadata", cls._check_metadata, content, issues, recommendations, categories)
        cls._run_check("links", cls._check_links, content, issues, recommendations, categories)
        cls._run_check("images", cls._check_images, content, issues, recommendations, categories)
        cls._run_check("accessibility", cls._check_accessibility, content, issues, recommendations, categories)
        cls._run_check("html", cls._check_html, content, issues, recommendations, categories)

        score = cls._calculate_score(categories)

        logger.info(
            "Technical HTML evaluation completed | score=%d | issues=%d | recommendations=%d",
            score, len(issues), len(recommendations),
        )

        return EvaluationResult(score=score, issues=issues, recommendations=recommendations)

    
    # CHECK RUNNER

    @classmethod
    def _run_check(cls, category, check, content, issues, recommendations, categories):
        category_issues = []
        category_recommendations = []

        logger.info("Running technical HTML check | category=%s", category)

        check(content, category_issues, category_recommendations)

        issues.extend(category_issues)
        recommendations.extend(category_recommendations)

        categories[category] = category_issues

        logger.info("Technical HTML check completed | category=%s | issues=%d", category, len(category_issues))


    # LOCATION HELPERS

    @classmethod
    def _nearest_stable_anchor(cls, tag):
        """
        Walk UP the tree from `tag` and return the first ancestor (including `tag` itself) that carries a stable identifying attribute, plus which attribute matched.

        Stable = it will not change between page loads (unlike an href packed with per-load tracking tokens such as ?uid=...&ga_id=...).

        Returns (attribute_name, value, owning_tag) or (None, None, None) if nothing stable was found anywhere up the tree.
        """
        node = tag

        while node is not None and getattr(node, "name", None) not in (None, "[document]"):
            for attr in cls.STABLE_ATTRS:
                value = node.get(attr)
                if value:
                    return attr, value, node
            node = node.parent

        return None, None, None

    @classmethod
    def _locate(cls, tag):
        """
        Build a short, human-readable breadcrumb for a tag, anchored at the nearest stable identifier (see STABLE_ATTRS) instead of always starting from <html>. This keeps the path short and greppable.

        Examples:
          div[data-id="BC-3186940"] > a.responsive-image (line 214)
          h3#about_heading (line 912)
        """
        chain = []
        node = tag
        stop_attr, stop_value, stop_node = cls._nearest_stable_anchor(tag)

        while node is not None and getattr(node, "name", None) not in (None, "[document]"):
            selector = node.name

            if node is stop_node:
                selector += f'[{stop_attr}="{stop_value}"]'
                chain.append(selector)
                break

            if node.get("class"):
                selector += "." + ".".join(node.get("class"))
            else:
                parent = node.parent
                siblings = (
                    parent.find_all(node.name, recursive=False)
                    if parent is not None
                    else []
                )
                if len(siblings) > 1:
                    position = siblings.index(node) + 1
                    selector += f":nth-of-type({position})"

            chain.append(selector)
            node = node.parent

        path = " > ".join(reversed(chain))
        line = getattr(tag, "sourceline", None)

        return f"{path} (line {line})" if line else path

    @classmethod
    def _css_selector(cls, tag):
        """
        Build a CSS selector a developer can paste directly into their browser's DevTools Console to jump straight to this element:

            document.querySelector('div[data-id="BC-3186940"] a.availability-button')

        Anchored the same way as _locate(): at the nearest stable attribute, so it still works after the page reloads and any tracking tokens in href/query strings change.
        """
        stop_attr, stop_value, stop_node = cls._nearest_stable_anchor(tag)

        if stop_node is None:
            # Nothing stable anywhere up the tree - fall back to a full tag-name path from <html>. Rare, but keeps this usable.
            parts = []
            node = tag
            while node is not None and getattr(node, "name", None) not in (None, "[document]"):
                parts.append(node.name)
                node = node.parent
            return " > ".join(reversed(parts))

        # Path from the stable ancestor DOWN to the target tag.
        parts = []
        node = tag
        while node is not None and node is not stop_node:
            piece = node.name
            if node.get("class"):
                piece += "." + ".".join(node.get("class"))
            parts.append(piece)
            node = node.parent

        anchor_selector = f'{stop_node.name}[{stop_attr}="{stop_value}"]'
        parts.append(anchor_selector)

        return " ".join(reversed(parts))

    @classmethod
    def _snippet(cls, tag):
        """Return a truncated outer-HTML snippet for a quick sanity check."""
        html = str(tag)

        if len(html) > cls.SNIPPET_LIMIT:
            html = html[: cls.SNIPPET_LIMIT].rstrip() + "..."

        return html

    @staticmethod
    def _describe(problem, *, location=None, selector=None, previous=None, html=None):
        """
        Compose a clean, multi-line, labeled issue description that is easy to scan - never a single run-on sentence.
        """
        lines = [problem, ""]

        if previous:
            lines.append(f"Previous Heading: {previous}")
        if location:
            lines.append(f"Location: {location}")
        if selector:
            lines.append(f"Selector (paste into DevTools Console as document.querySelector('...')): {selector}")
        if html:
            lines.append(f"HTML: {html}")

        return "\n".join(lines)

    @staticmethod
    def _recommend(action, *, location=None, selector=None):
        """
        Compose a clean, multi-line, labeled recommendation - what to do and exactly where to do it.
        """
        lines = [action, ""]

        if location:
            lines.append(f"Location: {location}")
        if selector:
            lines.append(f"Selector: {selector}")

        return "\n".join(lines)

    # @staticmethod
    # def _describe(problem, *, location=None, selector=None, previous=None, html=None):
    #     """
    #     Compose a clean, Markdown-safe issue description.

    #     Uses BLANK lines ("\\n\\n") between blocks, since Markdown
    #     renderers collapse single "\\n" into a plain space - a single
    #     newline produces no visible line break at all. Location,
    #     Selector, and HTML are wrapped in backticks so they render as
    #     monospace and get automatic wrapping/horizontal-scroll from the
    #     Markdown renderer's own code styling, instead of overflowing
    #     the card as raw unbroken text.
    #     """
    #     blocks = [problem]

    #     if previous:
    #         blocks.append(f"**Previous Heading:** `{previous}`")
    #     if location:
    #         blocks.append(f"**Location:** `{location}`")
    #     if selector:
    #         blocks.append(
    #             "**Selector** (paste into DevTools Console as "
    #             f"`document.querySelector('...')`):\n\n`{selector}`"
    #         )
    #     if html:
    #         blocks.append(f"**HTML:**\n\n```html\n{html}\n```")

    #     return "\n\n".join(blocks)

    # @staticmethod
    # def _recommend(action, *, location=None, selector=None):
    #     """
    #     Compose a clean, Markdown-safe recommendation. Same reasoning
    #     as _describe() above - blank-line-separated blocks, backticks
    #     around anything long/technical.
    #     """
    #     blocks = [action]

    #     if location:
    #         blocks.append(f"**Location:** `{location}`")
    #     if selector:
    #         blocks.append(f"**Selector:** `{selector}`")

    #     return "\n\n".join(blocks)

    @classmethod
    def _accessible_name(cls, tag):
        """
        Compute an element's real accessible name, mirroring the order browsers/screen readers actually use:

            1. aria-label
            2. visible text content
            3. alt text of a nested <img> (e.g. an icon-only link)
            4. title attribute (last resort)

        A link wrapping ONLY an <img alt="Booking.com"> with no visible text is NOT silent to a screen reader - it announces "Booking.com, link". Checking only tag.get_text() misses this and produces false "empty anchor" positives.
        """
        aria_label = (tag.get("aria-label") or "").strip()
        if aria_label:
            return aria_label

        text = tag.get_text(" ", strip=True)
        if text:
            return text

        image = tag.find("img")
        if image:
            image_alt = (image.get("alt") or "").strip()
            if image_alt:
                return image_alt

        title = (tag.get("title") or "").strip()
        if title:
            return title

        return ""


    # STRUCTURE

    @staticmethod
    def _check_structure(content, issues, recommendations):
        TechnicalHTMLEvaluator._check_basic_html_structure(content, issues, recommendations)
        TechnicalHTMLEvaluator._check_duplicate_h1(content, issues, recommendations)
        TechnicalHTMLEvaluator._check_heading_order(content, issues, recommendations)
        TechnicalHTMLEvaluator._check_duplicate_ids(content, issues, recommendations)

    @staticmethod
    def _check_basic_html_structure(content, issues, recommendations):
        required_tags = ("html", "head", "body")

        for tag_name in required_tags:
            if content.soup.find(tag_name):
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Missing HTML Structure",
                    description=(
                        f"The page is missing the required <{tag_name}> element.\n\n"
                        f"Every page needs a <html>, <head>, and <body> element to be "
                        f"valid, parseable, and reliably rendered across browsers."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Fix HTML Structure",
                    description=f"Add the missing <{tag_name}> element to the page structure.",
                )
            )

    @staticmethod
    def _check_duplicate_h1(content, issues, recommendations):
        h1_tags = content.soup.find_all("h1")

        if len(h1_tags) <= 1:
            return

        for tag in h1_tags[1:]:
            text = tag.get_text(" ", strip=True)
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="Medium",
                    title="Multiple H1 Tags",
                    description=TechnicalHTMLEvaluator._describe(
                        f"An additional H1 heading, \"{text or '[empty H1]'}\", was found on the page.\n"
                        f"A page should generally have only ONE H1 - it represents the page's main topic.",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Reduce Multiple H1 Tags",
                    description=TechnicalHTMLEvaluator._recommend(
                        f"Keep one primary H1 for the page. Convert the heading "
                        f"\"{text or '[empty H1]'}\" to an H2 or H3 if it represents a subsection.",
                        location=location,
                        selector=selector,
                    ),
                )
            )

    @staticmethod
    def _check_heading_order(content, issues, recommendations):
        headings = content.soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

        previous_level = None
        previous_text = ""
        previous_location = ""

        for tag in headings:
            level = int(tag.name[1])
            text = tag.get_text(" ", strip=True)
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)

            if previous_level is not None and level > previous_level + 1:
                snippet = TechnicalHTMLEvaluator._snippet(tag)
                previous_label = (
                    f"\"{previous_text or '[empty heading]'}\" (H{previous_level}) at {previous_location}"
                )

                issues.append(
                    Issue(
                        severity="Medium",
                        title="Invalid Heading Order",
                        description=TechnicalHTMLEvaluator._describe(
                            f"Heading \"{text or '[empty heading]'}\" is an H{level}, which skips ahead "
                            f"from H{previous_level} instead of stepping down one level at a time.\n"
                            f"Screen reader users navigate by heading level, so skipped levels make the "
                            f"page structure confusing to follow.",
                            location=location,
                            selector=selector,
                            previous=previous_label,
                            html=snippet,
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Heading Hierarchy",
                        description=TechnicalHTMLEvaluator._recommend(
                            f"Change \"{text or '[empty heading]'}\" from H{level} to H{previous_level + 1} "
                            f"so the hierarchy steps down one level at a time instead of skipping from "
                            f"H{previous_level} to H{level}.",
                            location=location,
                            selector=selector,
                        ),
                    )
                )

            previous_level = level
            previous_text = text
            previous_location = location

    @staticmethod
    def _check_duplicate_ids(content, issues, recommendations):
        tags_with_id = content.soup.find_all(id=True)
        counts = Counter(tag.get("id", "").strip() for tag in tags_with_id)

        for tag in tags_with_id:
            html_id = tag.get("id", "").strip()
            count = counts.get(html_id, 0)

            if not html_id or count <= 1:
                continue

            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="Medium",
                    title="Duplicate HTML ID",
                    description=TechnicalHTMLEvaluator._describe(
                        f"The HTML id \"{html_id}\" appears {count} times on the page.\n"
                        f"An id must be unique - duplicates break CSS/JS that target it by id, and "
                        f"confuse assistive technology that relies on ids for labeling.",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Make HTML IDs Unique",
                    description=TechnicalHTMLEvaluator._recommend(
                        f"Rename or remove one of the duplicate id=\"{html_id}\" occurrences. "
                        f"Each id should identify only one element on the page.",
                        location=location,
                        selector=selector,
                    ),
                )
            )


    # METADATA

    @staticmethod
    def _check_metadata(content, issues, recommendations):
        TechnicalHTMLEvaluator._check_title(content, issues, recommendations)
        TechnicalHTMLEvaluator._check_meta_description(content, issues, recommendations)

    @staticmethod
    def _check_title(content, issues, recommendations):
        title = (content.title or "").strip()

        if title:
            return

        issues.append(
            Issue(
                severity="High",
                title="Missing HTML Title",
                description=(
                    f"No <title> element was found for page \"{content.url}\".\n\n"
                    f"The <title> tag is what shows in browser tabs and search results - "
                    f"without it, the page has no name in search engines or bookmarks."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add HTML Title",
                description=f"Add a descriptive, unique <title> element inside <head> for \"{content.url}\".",
            )
        )

    @staticmethod
    def _check_meta_description(content, issues, recommendations):
        description = (content.meta_description or "").strip()

        if description:
            return

        issues.append(
            Issue(
                severity="Medium",
                title="Missing Meta Description",
                description=(
                    f"No meta description was found for \"{content.url}\".\n\n"
                    f"Search engines often show the meta description as the preview snippet "
                    f"under the page title in search results."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add Meta Description",
                description=f"Add a <meta name=\"description\" content=\"...\"> summarizing \"{content.url}\".",
            )
        )


    # LINKS

    @classmethod
    def _check_links(cls, content, issues, recommendations):
        cls._check_missing_href(content, issues, recommendations)
        cls._check_broken_links(content, issues, recommendations)

    @staticmethod
    def _check_missing_href(content, issues, recommendations):
        """
        The single source of truth for "anchor with no working href". (Previously this same problem was reported twice - once here and again under the "html" category - double-penalizing one bug.)
        """
        for tag in content.soup.find_all("a"):
            href = (tag.get("href") or "").strip()

            if href:
                continue

            name = TechnicalHTMLEvaluator._accessible_name(tag)
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="High",
                    title="Missing href Attribute",
                    description=TechnicalHTMLEvaluator._describe(
                        f"An anchor labeled \"{name or '[no accessible name]'}\" has no href attribute.\n"
                        f"Without an href, this is not a real, focusable, keyboard-usable link - it will "
                        f"not work for keyboard users, screen readers, or search engine crawlers.",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add href to Anchor",
                    description=TechnicalHTMLEvaluator._recommend(
                        f"Add a valid href pointing to the intended destination. If this element only "
                        f"triggers a JavaScript action rather than navigating anywhere, use a <button> "
                        f"instead of an <a> tag.",
                        location=location,
                        selector=selector,
                    ),
                )
            )

    @classmethod
    def _check_broken_links(cls, content, issues, recommendations):
        links = []

        for link in content.links:
            href = (link.href or "").strip()

            if not href:
                continue

            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            links.append((link, urljoin(content.url, href)))

        if not links:
            return

        logger.info(
            "Checking links concurrently | count=%d | workers=%d",
            len(links), min(cls.MAX_WORKERS, len(links)),
        )

        with ThreadPoolExecutor(max_workers=min(cls.MAX_WORKERS, len(links))) as executor:
            futures = {
                executor.submit(cls._request_url, absolute_url): (link, absolute_url)
                for link, absolute_url in links
            }

            for future in as_completed(futures):
                link, absolute_url = futures[future]

                try:
                    status = future.result()
                except Exception:
                    logger.exception("Unexpected link validation error | url=%s", absolute_url)
                    continue

                label = link.text or "[empty]"

                if status is None:
                    issues.append(
                        Issue(
                            severity="High",
                            title="Inaccessible Link",
                            description=(
                                f"The link labeled \"{label}\" points to:\n{absolute_url}\n\n"
                                f"That destination could not be reached at all (timed out, DNS failure, "
                                f"or connection refused)."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Inaccessible Link",
                            description=(
                                f"Review the link labeled \"{label}\".\n"
                                f"Destination: {absolute_url}\n"
                                f"Update it to a reachable URL, or remove the link if the destination no "
                                f"longer exists."
                            ),
                        )
                    )

                elif status >= 400:
                    issues.append(
                        Issue(
                            severity="High",
                            title="Broken Link",
                            description=(
                                f"The link labeled \"{label}\" points to:\n{absolute_url}\n\n"
                                f"That destination returned HTTP status {status}."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Link",
                            description=(
                                f"Review the link labeled \"{label}\".\n"
                                f"Destination: {absolute_url}\n"
                                f"It returned HTTP {status}. Replace it with a valid destination or remove it."
                            ),
                        )
                    )

    
    # IMAGES
    
    @classmethod
    def _check_images(cls, content, issues, recommendations):
        """
        Structural/availability image checks only. Whether an image has
        ALT text is an ACCESSIBILITY concern and is checked exactly once,
        under _check_accessibility - not duplicated here.
        """
        cls._check_missing_image_src(content, issues, recommendations)
        cls._check_broken_images(content, issues, recommendations)

    @staticmethod
    def _check_missing_image_src(content, issues, recommendations):
        for tag in content.soup.find_all("img"):
            src = (tag.get("src") or "").strip()

            if src:
                continue

            alt = (tag.get("alt") or "").strip()
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="High",
                    title="Missing Image Source",
                    description=TechnicalHTMLEvaluator._describe(
                        f"An <img> element has no src attribute, so no image can load here.\n"
                        f"ALT text on this element: \"{alt or '[empty]'}\"",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Image Source",
                    description=TechnicalHTMLEvaluator._recommend(
                        "Add a valid src attribute pointing to an actual image file.",
                        location=location,
                        selector=selector,
                    ),
                )
            )

    @classmethod
    def _check_broken_images(cls, content, issues, recommendations):
        images = []

        for image in content.images:
            src = (image.src or "").strip()

            if not src:
                continue

            images.append((image, urljoin(content.url, src)))

        if not images:
            return

        logger.info(
            "Checking images concurrently | count=%d | workers=%d",
            len(images), min(cls.MAX_WORKERS, len(images)),
        )

        with ThreadPoolExecutor(max_workers=min(cls.MAX_WORKERS, len(images))) as executor:
            futures = {
                executor.submit(cls._request_url, absolute_url): (image, absolute_url)
                for image, absolute_url in images
            }

            for future in as_completed(futures):
                image, absolute_url = futures[future]

                try:
                    status = future.result()
                except Exception:
                    logger.exception("Unexpected image validation error | url=%s", absolute_url)
                    continue

                if status is None:
                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Inaccessible Image",
                            description=f"This image could not be reached:\n{absolute_url}",
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Inaccessible Image",
                            description=(
                                f"Verify that this image source exists and is publicly accessible:\n"
                                f"{absolute_url}\n"
                                f"Replace the source if the image is no longer available."
                            ),
                        )
                    )

                elif status >= 400:
                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Broken Image",
                            description=(
                                f"This image source returned HTTP status {status}:\n{absolute_url}"
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Image",
                            description=(
                                f"Replace or repair this image source, which returned HTTP {status}:\n"
                                f"{absolute_url}"
                            ),
                        )
                    )


    # ACCESSIBILITY

    @classmethod
    def _check_accessibility(cls, content, issues, recommendations):
        cls._check_missing_image_alt(content, issues, recommendations)
        cls._check_empty_accessible_name(content, issues, recommendations)
        cls._check_missing_lang_attribute(content, issues, recommendations)

    @staticmethod
    def _check_missing_image_alt(content, issues, recommendations):
        """
        The single source of truth for "image missing ALT text".
        (Previously this same problem was reported twice - once under
        "images" and again here - double-penalizing one bug.)
        """
        for tag in content.soup.find_all("img"):
            alt = tag.get("alt")

            if alt is not None:
                continue

            src = (tag.get("src") or "").strip()
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="Medium",
                    title="Missing Image ALT Attribute",
                    description=TechnicalHTMLEvaluator._describe(
                        f"An image has no alt attribute at all.\n"
                        f"Image source: {src or '[missing src]'}\n"
                        f"Screen readers cannot describe this image to visually impaired users, and "
                        f"search engines cannot index what it depicts.",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Image ALT Text",
                    description=TechnicalHTMLEvaluator._recommend(
                        f"Add a meaningful alt attribute describing what this image shows. "
                        f"If the image is purely decorative, use alt=\"\" (empty, but present) "
                        f"so screen readers skip it intentionally rather than announcing nothing.",
                        location=location,
                        selector=selector,
                    ),
                )
            )

    @staticmethod
    def _check_empty_accessible_name(content, issues, recommendations):
        """
        Flags anchors that have NO real accessible name - checking text, aria-label, a nested image's alt, and title, in that priority order (see _accessible_name). An icon-only link with a proper alt on its inner <img> is NOT flagged here; only links a screen reader would announce with no label at all are.
        """
        for tag in content.soup.find_all("a"):
            name = TechnicalHTMLEvaluator._accessible_name(tag)

            if name:
                continue

            href = (tag.get("href") or "").strip()
            location = TechnicalHTMLEvaluator._locate(tag)
            selector = TechnicalHTMLEvaluator._css_selector(tag)
            snippet = TechnicalHTMLEvaluator._snippet(tag)

            issues.append(
                Issue(
                    severity="Low",
                    title="Empty Accessible Name",
                    description=TechnicalHTMLEvaluator._describe(
                        f"This anchor has no visible text, no aria-label, no title, and its inner "
                        f"image (if any) has no alt text either.\n"
                        f"A screen reader has nothing to announce for it besides \"link\" - the user "
                        f"has no idea where it goes.\n"
                        f"href: {href or '[missing href]'}",
                        location=location,
                        selector=selector,
                        html=snippet,
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add an Accessible Name",
                    description=TechnicalHTMLEvaluator._recommend(
                        "Add visible text, an aria-label, or a descriptive alt attribute on the "
                        "image inside this link, so it announces something meaningful.",
                        location=location,
                        selector=selector,
                    ),
                )
            )

    @staticmethod
    def _check_missing_lang_attribute(content, issues, recommendations):
        html_tag = content.soup.find("html")

        if html_tag is None:
            return

        lang = (html_tag.get("lang") or "").strip()

        if lang:
            return

        issues.append(
            Issue(
                severity="Low",
                title="Missing lang Attribute",
                description=(
                    "The <html> element has no lang attribute (e.g. lang=\"en\").\n\n"
                    "Screen readers use this to choose the correct pronunciation/voice, and "
                    "browsers use it for translation prompts."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add lang Attribute",
                description="Add a lang attribute to <html>, e.g. <html lang=\"en\">.",
            )
        )


    # HTML - GENERAL VALIDITY (distinct from links/images/accessibility)

    @staticmethod
    def _check_html(content, issues, recommendations):
        TechnicalHTMLEvaluator._check_missing_viewport(content, issues, recommendations)
        TechnicalHTMLEvaluator._check_missing_charset(content, issues, recommendations)

    @staticmethod
    def _check_missing_viewport(content, issues, recommendations):
        viewport = content.soup.find("meta", attrs={"name": "viewport"})

        if viewport is not None:
            return

        issues.append(
            Issue(
                severity="Medium",
                title="Missing Viewport Meta Tag",
                description=(
                    "No <meta name=\"viewport\"> tag was found in <head>.\n\n"
                    "Without it, mobile browsers render the page at desktop width and "
                    "shrink it to fit, producing tiny, hard-to-read text and broken layouts "
                    "on phones."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add Viewport Meta Tag",
                description=(
                    "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> "
                    "inside <head> so the page renders correctly on mobile devices."
                ),
            )
        )

    @staticmethod
    def _check_missing_charset(content, issues, recommendations):
        charset = content.soup.find("meta", attrs={"charset": True}) or content.soup.find(
            "meta", attrs={"http-equiv": "Content-Type"}
        )

        if charset is not None:
            return

        issues.append(
            Issue(
                severity="Low",
                title="Missing Charset Declaration",
                description=(
                    "No <meta charset=\"...\"> tag was found in <head>.\n\n"
                    "Without an explicit charset, browsers must guess the page's text "
                    "encoding, which can cause special characters (accents, currency "
                    "symbols, etc.) to render incorrectly."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add Charset Declaration",
                description="Add <meta charset=\"UTF-8\"> as the first element inside <head>.",
            )
        )


    # HTTP

    @classmethod
    def _request_url(cls, url):
        try:
            response = requests.head(url, allow_redirects=True, timeout=cls.REQUEST_TIMEOUT, headers=cls.HEADERS)

            if response.status_code in (405, 403):
                response = requests.get(
                    url, allow_redirects=True, timeout=cls.REQUEST_TIMEOUT, headers=cls.HEADERS, stream=True
                )

            logger.info("URL checked | url=%s | status=%d", url, response.status_code)

            return response.status_code

        except requests.RequestException:
            logger.warning("URL could not be reached | url=%s", url)
            return None


    # SCORING

    @classmethod
    def _calculate_score(cls, categories):
        score = 100

        for category, penalty in cls.PENALTIES.items():
            category_issues = categories.get(category, [])

            if not category_issues:
                continue

            score -= penalty

            logger.info(
                "Category penalty applied | category=%s | penalty=%d | issues=%d",
                category, penalty, len(category_issues),
            )

        return max(score, 0)
