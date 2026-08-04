import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    Recommendation,
)

logger = logging.getLogger(__name__)


class TechnicalHTMLEvaluator:
    """
    Evaluates the technical HTML quality of a webpage.

    Issues are reported individually with specific context.
    Scoring is calculated by category so repeated issues do not
    unfairly destroy the overall technical HTML score.
    """

    MAX_WORKERS = 10
    REQUEST_TIMEOUT = 5
    HEADERS = {"User-Agent": "Mozilla/5.0"}

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
        logger.info(
            "Technical HTML evaluation started | url=%s",
            content.url,
        )

        issues = []
        recommendations = []
        categories = {}

        cls._run_check(
            "structure",
            cls._check_structure,
            content,
            issues,
            recommendations,
            categories,
        )

        cls._run_check(
            "metadata",
            cls._check_metadata,
            content,
            issues,
            recommendations,
            categories,
        )

        cls._run_check(
            "links",
            cls._check_links,
            content,
            issues,
            recommendations,
            categories,
        )

        cls._run_check(
            "images",
            cls._check_images,
            content,
            issues,
            recommendations,
            categories,
        )

        cls._run_check(
            "accessibility",
            cls._check_accessibility,
            content,
            issues,
            recommendations,
            categories,
        )

        cls._run_check(
            "html",
            cls._check_html,
            content,
            issues,
            recommendations,
            categories,
        )

        score = cls._calculate_score(categories)

        logger.info(
            "Technical HTML evaluation completed | "
            "score=%d | issues=%d | recommendations=%d",
            score,
            len(issues),
            len(recommendations),
        )

        return EvaluationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
        )

    # ============================================================
    # CHECK RUNNER
    # ============================================================

    @classmethod
    def _run_check(
        cls,
        category,
        check,
        content,
        issues,
        recommendations,
        categories,
    ):
        category_issues = []
        category_recommendations = []

        logger.info(
            "Running technical HTML check | category=%s",
            category,
        )

        check(
            content,
            category_issues,
            category_recommendations,
        )

        issues.extend(category_issues)
        recommendations.extend(category_recommendations)

        categories[category] = category_issues

        logger.info(
            "Technical HTML check completed | "
            "category=%s | issues=%d",
            category,
            len(category_issues),
        )

    # ============================================================
    # STRUCTURE
    # ============================================================

    @staticmethod
    def _check_structure(
        content,
        issues,
        recommendations,
    ):
        TechnicalHTMLEvaluator._check_basic_html_structure(
            content,
            issues,
            recommendations,
        )

        TechnicalHTMLEvaluator._check_duplicate_h1(
            content,
            issues,
            recommendations,
        )

        TechnicalHTMLEvaluator._check_heading_order(
            content,
            issues,
            recommendations,
        )

        TechnicalHTMLEvaluator._check_duplicate_ids(
            content,
            issues,
            recommendations,
        )

    @staticmethod
    def _check_basic_html_structure(
        content,
        issues,
        recommendations,
    ):
        required_tags = ("html", "head", "body")

        for tag_name in required_tags:
            if content.soup.find(tag_name):
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Missing HTML Structure",
                    description=(
                        f"The page is missing the required "
                        f"<{tag_name}> element."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Fix HTML Structure",
                    description=(
                        f"Add the missing <{tag_name}> element "
                        f"to the page structure."
                    ),
                )
            )

    @staticmethod
    def _check_duplicate_h1(
        content,
        issues,
        recommendations,
    ):
        h1_tags = content.soup.find_all("h1")

        if len(h1_tags) <= 1:
            return

        for index, tag in enumerate(h1_tags[1:], start=2):
            text = tag.get_text(" ", strip=True)

            issues.append(
                Issue(
                    severity="Medium",
                    title="Multiple H1 Tags",
                    description=(
                        f"Additional H1 found at occurrence #{index}: "
                        f"'{text or '[empty H1]'}'."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Reduce Multiple H1 Tags",
                    description=(
                        f"The H1 '{text or '[empty H1]'}' is an "
                        f"additional H1 on the page. Keep one primary "
                        f"H1 and convert this heading to an appropriate "
                        f"H2 or H3 if it represents a subsection."
                    ),
                )
            )

    @staticmethod
    def _check_heading_order(
        content,
        issues,
        recommendations,
    ):
        headings = content.soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6"]
        )

        previous_level = None
        previous_text = ""

        for tag in headings:
            level = int(tag.name[1])
            text = tag.get_text(" ", strip=True)

            if (
                previous_level is not None
                and level > previous_level + 1
            ):
                issues.append(
                    Issue(
                        severity="Medium",
                        title="Invalid Heading Order",
                        description=(
                            f"Heading '{text or '[empty heading]'}' "
                            f"is H{level}, but the previous heading "
                            f"'{previous_text or '[empty heading]'}' "
                            f"is H{previous_level}. The hierarchy "
                            f"jumps from H{previous_level} to H{level}."
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Heading Hierarchy",
                        description=(
                            f"Change '{text or '[empty heading]'}' "
                            f"from H{level} to an appropriate heading "
                            f"level so the hierarchy does not skip "
                            f"from H{previous_level} to H{level}."
                        ),
                    )
                )

            previous_level = level
            previous_text = text

    @staticmethod
    def _check_duplicate_ids(
        content,
        issues,
        recommendations,
    ):
        ids = [
            tag.get("id", "").strip()
            for tag in content.soup.find_all(id=True)
        ]

        counts = Counter(ids)

        for html_id, count in counts.items():
            if not html_id or count <= 1:
                continue

            issues.append(
                Issue(
                    severity="Medium",
                    title="Duplicate HTML ID",
                    description=(
                        f"The HTML id '{html_id}' appears "
                        f"{count} times on the page."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Make HTML IDs Unique",
                    description=(
                        f"Rename or remove duplicate occurrences of "
                        f"id='{html_id}'. Each HTML id should identify "
                        f"only one element on the page."
                    ),
                )
            )

    # ============================================================
    # METADATA
    # ============================================================

    @staticmethod
    def _check_metadata(
        content,
        issues,
        recommendations,
    ):
        TechnicalHTMLEvaluator._check_title(
            content,
            issues,
            recommendations,
        )

        TechnicalHTMLEvaluator._check_meta_description(
            content,
            issues,
            recommendations,
        )

    @staticmethod
    def _check_title(
        content,
        issues,
        recommendations,
    ):
        title = (content.title or "").strip()

        if title:
            return

        issues.append(
            Issue(
                severity="High",
                title="Missing HTML Title",
                description=(
                    f"No <title> element was found for page "
                    f"'{content.url}'."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add HTML Title",
                description=(
                    f"Add a descriptive and unique <title> element "
                    f"for the page '{content.url}'."
                ),
            )
        )

    @staticmethod
    def _check_meta_description(
        content,
        issues,
        recommendations,
    ):
        description = (
            content.meta_description or ""
        ).strip()

        if description:
            return

        issues.append(
            Issue(
                severity="Medium",
                title="Missing Meta Description",
                description=(
                    f"No meta description was found for "
                    f"'{content.url}'."
                ),
            )
        )

        recommendations.append(
            Recommendation(
                title="Add Meta Description",
                description=(
                    f"Add a meaningful meta description describing "
                    f"the content of '{content.url}'."
                ),
            )
        )

    # ============================================================
    # LINKS
    # ============================================================

    @classmethod
    def _check_links(
        cls,
        content,
        issues,
        recommendations,
    ):
        cls._check_empty_links(
            content,
            issues,
            recommendations,
        )

        cls._check_missing_href(
            content,
            issues,
            recommendations,
        )

        cls._check_broken_links(
            content,
            issues,
            recommendations,
        )

    @staticmethod
    def _check_empty_links(
        content,
        issues,
        recommendations,
    ):
        for link in content.links:
            text = (link.text or "").strip()
            href = (link.href or "").strip()

            if text:
                continue

            issues.append(
                Issue(
                    severity="Low",
                    title="Empty Anchor Text",
                    description=(
                        f"An anchor has empty visible text. "
                        f"href='{href or '[missing href]'}'."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Descriptive Anchor Text",
                    description=(
                        f"Add visible, descriptive anchor text to "
                        f"the link with href='{href or '[missing href]'}' "
                        f"so users and search engines can understand "
                        f"the link destination."
                    ),
                )
            )

    @staticmethod
    def _check_missing_href(
        content,
        issues,
        recommendations,
    ):
        for index, tag in enumerate(
            content.soup.find_all("a"),
            start=1,
        ):
            href = tag.get("href")
            text = tag.get_text(" ", strip=True)

            if href:
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Missing href Attribute",
                    description=(
                        f"Anchor #{index} is missing the href "
                        f"attribute. Anchor text: "
                        f"'{text or '[empty]'}'."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add href to Anchor",
                    description=(
                        f"Add a valid href to anchor #{index} "
                        f"('{text or '[empty]'}'). The href should "
                        f"point to the intended destination."
                    ),
                )
            )

    @classmethod
    def _check_broken_links(
        cls,
        content,
        issues,
        recommendations,
    ):
        links = []

        for link in content.links:
            href = (link.href or "").strip()

            if not href:
                continue

            if href.startswith(
                ("#", "mailto:", "tel:", "javascript:")
            ):
                continue

            links.append(
                (
                    link,
                    urljoin(content.url, href),
                )
            )

        if not links:
            return

        logger.info(
            "Checking links concurrently | count=%d | workers=%d",
            len(links),
            min(cls.MAX_WORKERS, len(links)),
        )

        with ThreadPoolExecutor(
            max_workers=min(cls.MAX_WORKERS, len(links))
        ) as executor:
            futures = {
                executor.submit(
                    cls._request_url,
                    absolute_url,
                ): (link, absolute_url)
                for link, absolute_url in links
            }

            for future in as_completed(futures):
                link, absolute_url = futures[future]

                try:
                    status = future.result()
                except Exception:
                    logger.exception(
                        "Unexpected link validation error | url=%s",
                        absolute_url,
                    )
                    continue

                if status is None:
                    issues.append(
                        Issue(
                            severity="High",
                            title="Inaccessible Link",
                            description=(
                                f"Link text '{link.text or '[empty]'}' "
                                f"points to '{absolute_url}', but the "
                                f"destination could not be reached."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Inaccessible Link",
                            description=(
                                f"Review the link '{absolute_url}' "
                                f"used by anchor text "
                                f"'{link.text or '[empty]'}'. "
                                f"Update it to a reachable URL or "
                                f"remove the link if the destination "
                                f"no longer exists."
                            ),
                        )
                    )

                elif status >= 400:
                    issues.append(
                        Issue(
                            severity="High",
                            title="Broken Link",
                            description=(
                                f"Link text '{link.text or '[empty]'}' "
                                f"points to '{absolute_url}', which "
                                f"returned HTTP status {status}."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Link",
                            description=(
                                f"Review the link used by "
                                f"'{link.text or '[empty]'}': "
                                f"'{absolute_url}'. It returned "
                                f"HTTP {status}. Replace it with a "
                                f"valid destination or remove it."
                            ),
                        )
                    )

    # ============================================================
    # IMAGES
    # ============================================================

    @classmethod
    def _check_images(
        cls,
        content,
        issues,
        recommendations,
    ):
        cls._check_missing_image_alt(
            content,
            issues,
            recommendations,
        )

        cls._check_missing_image_src(
            content,
            issues,
            recommendations,
        )

        cls._check_broken_images(
            content,
            issues,
            recommendations,
        )

    @staticmethod
    def _check_missing_image_alt(
        content,
        issues,
        recommendations,
    ):
        for index, image in enumerate(
            content.images,
            start=1,
        ):
            src = (image.src or "").strip()
            alt = (image.alt or "").strip()

            if alt:
                continue

            issues.append(
                Issue(
                    severity="Medium",
                    title="Missing Image ALT",
                    description=(
                        f"Image #{index} is missing ALT text. "
                        f"Image source: '{src or '[missing src]'}'."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Image ALT Text",
                    description=(
                        f"Add meaningful ALT text to image #{index} "
                        f"('{src or '[missing src]'}') describing "
                        f"the image's purpose or content."
                    ),
                )
            )

    @staticmethod
    def _check_missing_image_src(
        content,
        issues,
        recommendations,
    ):
        for index, tag in enumerate(
            content.soup.find_all("img"),
            start=1,
        ):
            src = tag.get("src")
            alt = tag.get("alt", "").strip()

            if src:
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Missing Image Source",
                    description=(
                        f"Image #{index} is missing the src "
                        f"attribute. ALT text: "
                        f"'{alt or '[empty]'}'."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Image Source",
                    description=(
                        f"Add a valid src attribute to image #{index} "
                        f"with ALT text '{alt or '[empty]'}'."
                    ),
                )
            )

    @classmethod
    def _check_broken_images(
        cls,
        content,
        issues,
        recommendations,
    ):
        images = []

        for image in content.images:
            src = (image.src or "").strip()

            if not src:
                continue

            images.append(
                (
                    image,
                    urljoin(content.url, src),
                )
            )

        if not images:
            return

        logger.info(
            "Checking images concurrently | count=%d | workers=%d",
            len(images),
            min(cls.MAX_WORKERS, len(images)),
        )

        with ThreadPoolExecutor(
            max_workers=min(cls.MAX_WORKERS, len(images))
        ) as executor:
            futures = {
                executor.submit(
                    cls._request_url,
                    absolute_url,
                ): (image, absolute_url)
                for image, absolute_url in images
            }

            for future in as_completed(futures):
                image, absolute_url = futures[future]

                try:
                    status = future.result()
                except Exception:
                    logger.exception(
                        "Unexpected image validation error | url=%s",
                        absolute_url,
                    )
                    continue

                if status is None:
                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Inaccessible Image",
                            description=(
                                f"Image '{absolute_url}' could not "
                                f"be reached."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Inaccessible Image",
                            description=(
                                f"Verify that image source "
                                f"'{absolute_url}' exists and is "
                                f"accessible. Replace the source "
                                f"if the image is no longer available."
                            ),
                        )
                    )

                elif status >= 400:
                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Broken Image",
                            description=(
                                f"Image source '{absolute_url}' "
                                f"returned HTTP status {status}."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Image",
                            description=(
                                f"Replace or repair the image source "
                                f"'{absolute_url}', which returned "
                                f"HTTP {status}."
                            ),
                        )
                    )

    # ============================================================
    # ACCESSIBILITY
    # ============================================================

    @staticmethod
    def _check_accessibility(
        content,
        issues,
        recommendations,
    ):
        for index, tag in enumerate(
            content.soup.find_all("img"),
            start=1,
        ):
            alt = tag.get("alt")

            if alt is not None:
                continue

            src = tag.get("src", "")

            issues.append(
                Issue(
                    severity="Medium",
                    title="Missing Image Accessibility Attribute",
                    description=(
                        f"Image #{index} with source "
                        f"'{src or '[missing src]'}' does not "
                        f"contain an ALT attribute."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add ALT Attribute",
                    description=(
                        f"Add an ALT attribute to image #{index} "
                        f"('{src or '[missing src]'}')."
                    ),
                )
            )

    # ============================================================
    # HTML ATTRIBUTES / VALIDATION
    # ============================================================

    @staticmethod
    def _check_html(
        content,
        issues,
        recommendations,
    ):
        for index, tag in enumerate(
            content.soup.find_all("a"),
            start=1,
        ):
            if tag.get("href"):
                continue

            text = tag.get_text(" ", strip=True)

            issues.append(
                Issue(
                    severity="High",
                    title="Invalid Anchor Element",
                    description=(
                        f"Anchor #{index} with text "
                        f"'{text or '[empty]'}' has no href."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Complete Anchor Element",
                    description=(
                        f"Add a valid href to anchor #{index} "
                        f"('{text or '[empty]'}')."
                    ),
                )
            )

    # ============================================================
    # HTTP
    # ============================================================

    @classmethod
    def _request_url(cls, url):
        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=cls.REQUEST_TIMEOUT,
                headers=cls.HEADERS,
            )

            if response.status_code in (405, 403):
                response = requests.get(
                    url,
                    allow_redirects=True,
                    timeout=cls.REQUEST_TIMEOUT,
                    headers=cls.HEADERS,
                    stream=True,
                )

            logger.info(
                "URL checked | url=%s | status=%d",
                url,
                response.status_code,
            )

            return response.status_code

        except requests.RequestException:
            logger.warning(
                "URL could not be reached | url=%s",
                url,
            )
            return None

    # ============================================================
    # SCORING
    # ============================================================

    @classmethod
    def _calculate_score(cls, categories):
        score = 100

        for category, penalty in cls.PENALTIES.items():
            category_issues = categories.get(category, [])

            if not category_issues:
                continue

            score -= penalty

            logger.info(
                "Category penalty applied | "
                "category=%s | penalty=%d | issues=%d",
                category,
                penalty,
                len(category_issues),
            )

        return max(score, 0)

##working !!!

# import logging
# from urllib.parse import urljoin
# import requests

# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import (
#     EvaluationResult,
#     Issue,
#     Recommendation,
# )

# logger = logging.getLogger(__name__)


# class TechnicalHTMLEvaluator:
#     """
#     Evaluates the technical HTML quality of a webpage.
#     """

#     @classmethod
#     def evaluate(cls, content: WebsiteContent) -> EvaluationResult:
#         logger.info(
#             "Technical HTML evaluation started | url=%s",
#             content.url,
#         )
#         issues = []
#         recommendations = []
#         logger.info("Running title check.")
#         cls._check_title(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running meta description check.")
#         cls._check_meta_description(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running duplicate H1 check.")
#         cls._check_duplicate_h1(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running empty links check | links=%d", len(content.links))
#         cls._check_empty_links(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running missing image ALT check | images=%d", len(content.images))
#         cls._check_missing_image_alt(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running missing image SRC check.")
#         cls._check_missing_image_src(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running heading order check.")
#         cls._check_invalid_heading_order(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running duplicate ID check.")
#         cls._check_duplicate_ids(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running missing HTML attributes check.")
#         cls._check_missing_html_attributes(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info("Running basic HTML validation.")
#         cls._check_basic_html_validation(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info(
#             "Running broken link check | links=%d",
#             len(content.links),
#         )
#         cls._check_broken_links(
#             content,
#             issues,
#             recommendations,
#         )
#         logger.info(
#             "Running broken image check | images=%d",
#             len(content.images),
#         )
#         cls._check_broken_images(
#             content,
#             issues,
#             recommendations,
#         )
#         score = cls._calculate_score(issues)
#         logger.info(
#             "Technical HTML evaluation completed | score=%d | issues=%d | recommendations=%d",
#             score,
#             len(issues),
#             len(recommendations),
#         )
#         return EvaluationResult(
#             score=score,
#             issues=issues,
#             recommendations=recommendations,
#         )

#     @staticmethod
#     def _check_title(
#         content,
#         issues,
#         recommendations,
#     ):
#         if content.title:
#             return
#         issues.append(
#             Issue(
#                 severity="High",
#                 title="Missing HTML Title",
#                 description="The webpage does not contain a title tag.",
#             )
#         )
#         recommendations.append(
#             Recommendation(
#                 title="Add HTML Title",
#                 description="Add a descriptive and unique HTML title.",
#             )
#         )

#     @staticmethod
#     def _check_meta_description(
#         content,
#         issues,
#         recommendations,
#     ):
#         if content.meta_description:
#             return
#         issues.append(
#             Issue(
#                 severity="Medium",
#                 title="Missing Meta Description",
#                 description="No meta description was found.",
#             )
#         )
#         recommendations.append(
#             Recommendation(
#                 title="Add Meta Description",
#                 description="Provide a meaningful meta description.",
#             )
#         )

#     @staticmethod
#     def _check_duplicate_h1(
#         content,
#         issues,
#         recommendations,
#     ):
#         if len(content.headings.h1) <= 1:
#             return
#         issues.append(
#             Issue(
#                 severity="Medium",
#                 title="Multiple H1 Tags",
#                 description="A webpage should contain only one H1 heading.",
#             )
#         )
#         recommendations.append(
#             Recommendation(
#                 title="Keep One H1",
#                 description="Use a single H1 and move others to H2 or H3.",
#             )
#         )

#     @staticmethod
#     def _check_empty_links(
#         content,
#         issues,
#         recommendations,
#     ):
#         for link in content.links:
#             if link.text.strip():
#                 continue
#             issues.append(
#                 Issue(
#                     severity="Low",
#                     title="Empty Anchor Text",
#                     description=f"Link '{link.href}' has no visible text.",
#                 )
#             )
#             recommendations.append(
#                 Recommendation(
#                     title="Add Anchor Text",
#                     description="Provide descriptive anchor text for links.",
#                 )
#             )

#     @staticmethod
#     def _check_missing_image_alt(
#         content,
#         issues,
#         recommendations,
#     ):
#         for image in content.images:
#             if image.alt.strip():
#                 continue
#             issues.append(
#                 Issue(
#                     severity="Medium",
#                     title="Missing Image ALT",
#                     description=f"Image '{image.src}' has no ALT text.",
#                 )
#             )
#             recommendations.append(
#                 Recommendation(
#                     title="Add ALT Text",
#                     description="Every image should have meaningful ALT text.",
#                 )
#             )

#     @staticmethod
#     def _check_missing_image_src(
#         content,
#         issues,
#         recommendations,
#     ):
#         for image in content.images:
#             if image.src.strip():
#                 continue
#             issues.append(
#                 Issue(
#                     severity="High",
#                     title="Missing Image Source",
#                     description="An image tag is missing the src attribute.",
#                 )
#             )
#             recommendations.append(
#                 Recommendation(
#                     title="Provide Image Source",
#                     description="Every image must specify a valid src.",
#                 )
#             )

#     @staticmethod
#     def _check_invalid_heading_order(
#         content,
#         issues,
#         recommendations,
#     ):
#         heading_sequence = []
#         for tag in content.soup.find_all(
#             ["h1", "h2", "h3", "h4", "h5", "h6"]
#         ):
#             level = int(tag.name[1])
#             heading_sequence.append(level)
#         previous_level = 0
#         for level in heading_sequence:
#             if previous_level and level > previous_level + 1:
#                 issues.append(
#                     Issue(
#                         severity="Medium",
#                         title="Invalid Heading Order",
#                         description=(
#                             f"Heading level jumps from "
#                             f"H{previous_level} to H{level}."
#                         ),
#                     )
#                 )
#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Heading Hierarchy",
#                         description=(
#                             "Use sequential heading levels "
#                             "(H1 → H2 → H3)."
#                         ),
#                     )
#                 )
#                 return
#             previous_level = level

#     @staticmethod
#     def _check_duplicate_ids(
#         content,
#         issues,
#         recommendations,
#     ):
#         ids = []
#         for tag in content.soup.find_all(id=True):
#             ids.append(tag["id"])
#         duplicates = {
#             html_id
#             for html_id in ids
#             if ids.count(html_id) > 1
#         }
#         for html_id in duplicates:
#             issues.append(
#                 Issue(
#                     severity="Medium",
#                     title="Duplicate HTML ID",
#                     description=(
#                         f"Duplicate id '{html_id}' found."
#                     ),
#                 )
#             )
#             recommendations.append(
#                 Recommendation(
#                     title="Use Unique IDs",
#                     description=(
#                         "Every HTML id attribute should "
#                         "be unique."
#                     ),
#                 )
#             )

#     @staticmethod
#     def _check_missing_html_attributes(
#         content,
#         issues,
#         recommendations,
#     ):
#         for tag in content.soup.find_all("a"):
#             if not tag.get("href"):
#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Missing href Attribute",
#                         description="Anchor tag missing href.",
#                     )
#                 )
#                 recommendations.append(
#                     Recommendation(
#                         title="Add href",
#                         description="Every anchor should contain a valid href.",
#                     )
#                 )
#         for tag in content.soup.find_all("img"):
#             if not tag.get("src"):
#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Missing src Attribute",
#                         description="Image missing src attribute.",
#                     )
#                 )
#                 recommendations.append(
#                     Recommendation(
#                         title="Add Image Source",
#                         description="Every image should specify a src.",
#                     )
#                 )

#     @staticmethod
#     def _check_basic_html_validation(
#         content,
#         issues,
#         recommendations,
#     ):
#         required_tags = [
#             "html",
#             "head",
#             "body",
#         ]
#         for tag_name in required_tags:
#             if content.soup.find(tag_name):
#                 continue
#             issues.append(
#                 Issue(
#                     severity="High",
#                     title="Invalid HTML Structure",
#                     description=f"Missing <{tag_name}> tag.",
#                 )
#             )
#             recommendations.append(
#                 Recommendation(
#                     title="Fix HTML Structure",
#                     description=(
#                         f"Add the missing <{tag_name}> element."
#                     ),
#                 )
#             )

#     @staticmethod
#     def _check_broken_links(
#         content,
#         issues,
#         recommendations,
#     ):
#         headers = {
#             "User-Agent": "Mozilla/5.0",
#         }
#         timeout = 5
#         for link in content.links:
#             href = link.href.strip()
#             if not href:
#                 continue
#             if href.startswith(("#", "mailto:", "tel:", "javascript:")):
#                 continue
#             absolute_url = urljoin(
#                 content.url,
#                 href,
#             )
#             logger.info(
#                 "Checking link | url=%s",
#                 absolute_url,
#             )
#             try:
#                 response = requests.head(
#                     absolute_url,
#                     allow_redirects=True,
#                     timeout=timeout,
#                     headers=headers,
#                 )
#                 logger.info(
#                     "Link checked | url=%s | status=%d",
#                     absolute_url,
#                     response.status_code,
#                 )
#                 if response.status_code >= 400:
#                     issues.append(
#                         Issue(
#                             severity="High",
#                             title="Broken Link",
#                             description=(
#                                 f"'{absolute_url}' returned "
#                                 f"{response.status_code}."
#                             ),
#                         )
#                     )
#                     recommendations.append(
#                         Recommendation(
#                             title="Fix Broken Link",
#                             description=(
#                                 "Update or remove broken hyperlinks."
#                             ),
#                         )
#                     )
#             except requests.RequestException:
#                 logger.exception(
#                     "Link check failed | url=%s",
#                     absolute_url,
#                 )
#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Broken Link",
#                         description=(
#                             f"Unable to access '{absolute_url}'."
#                         ),
#                     )
#                 )
#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Broken Link",
#                         description=(
#                             "Ensure hyperlinks are reachable."
#                         ),
#                     )
#                 )

#     @staticmethod
#     def _check_broken_images(
#         content,
#         issues,
#         recommendations,
#     ):
#         headers = {
#             "User-Agent": "Mozilla/5.0",
#         }
#         timeout = 5
#         for image in content.images:
#             src = image.src.strip()
#             if not src:
#                 continue
#             absolute_url = urljoin(
#                 content.url,
#                 src,
#             )
#             logger.info(
#                 "Checking image | url=%s",
#                 absolute_url,
#             )
#             try:
#                 response = requests.head(
#                     absolute_url,
#                     allow_redirects=True,
#                     timeout=timeout,
#                     headers=headers,
#                 )
#                 logger.info(
#                     "Image checked | url=%s | status=%d",
#                     absolute_url,
#                     response.status_code,
#                 )
#                 if response.status_code >= 400:
#                     issues.append(
#                         Issue(
#                             severity="Medium",
#                             title="Broken Image",
#                             description=(
#                                 f"'{absolute_url}' returned "
#                                 f"{response.status_code}."
#                             ),
#                         )
#                     )
#                     recommendations.append(
#                         Recommendation(
#                             title="Fix Broken Image",
#                             description=(
#                                 "Replace or repair broken image sources."
#                             ),
#                         )
#                     )
#             except requests.RequestException:
#                 logger.exception(
#                     "Image check failed | url=%s",
#                     absolute_url,
#                 )
#                 issues.append(
#                     Issue(
#                         severity="Medium",
#                         title="Broken Image",
#                         description=(
#                             f"Unable to access '{absolute_url}'."
#                         )
#                     )
#                 )
#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Broken Image",
#                         description=(
#                             "Verify image URLs are accessible."
#                         )
#                     )
#                 )

#     @staticmethod
#     def _calculate_score(issues):
#         score = 100
#         penalties = {
#             "High": 15,
#             "Medium": 8,
#             "Low": 3,
#         }
#         for issue in issues:
#             score -= penalties.get(issue.severity, 0)
#         return max(score, 0)



# from urllib.parse import urljoin
# import requests

# from evaluator.extractor.schemas import WebsiteContent
# from evaluator.evaluators.schemas import (
#     EvaluationResult,
#     Issue,
#     Recommendation,
# )


# class TechnicalHTMLEvaluator:
#     """
#     Evaluates the technical HTML quality of a webpage.
#     """

#     @classmethod
#     def evaluate(cls, content: WebsiteContent) -> EvaluationResult:

#         issues = []
#         recommendations = []

#         cls._check_title(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_meta_description(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_duplicate_h1(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_empty_links(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_missing_image_alt(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_missing_image_src(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_invalid_heading_order(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_duplicate_ids(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_missing_html_attributes(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_basic_html_validation(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_broken_links(
#             content,
#             issues,
#             recommendations,
#         )

#         cls._check_broken_images(
#             content,
#             issues,
#             recommendations,
#         )

#         score = cls._calculate_score(issues)

#         return EvaluationResult(
#             score=score,
#             issues=issues,
#             recommendations=recommendations,
#         )

#     @staticmethod
#     def _check_title(
#         content,
#         issues,
#         recommendations,
#     ):

#         if content.title:
#             return

#         issues.append(
#             Issue(
#                 severity="High",
#                 title="Missing HTML Title",
#                 description="The webpage does not contain a title tag.",
#             )
#         )

#         recommendations.append(
#             Recommendation(
#                 title="Add HTML Title",
#                 description="Add a descriptive and unique HTML title.",
#             )
#         )

#     @staticmethod
#     def _check_meta_description(
#         content,
#         issues,
#         recommendations,
#     ):

#         if content.meta_description:
#             return

#         issues.append(
#             Issue(
#                 severity="Medium",
#                 title="Missing Meta Description",
#                 description="No meta description was found.",
#             )
#         )

#         recommendations.append(
#             Recommendation(
#                 title="Add Meta Description",
#                 description="Provide a meaningful meta description.",
#             )
#         )

#     @staticmethod
#     def _check_duplicate_h1(
#         content,
#         issues,
#         recommendations,
#     ):

#         if len(content.headings.h1) <= 1:
#             return

#         issues.append(
#             Issue(
#                 severity="Medium",
#                 title="Multiple H1 Tags",
#                 description="A webpage should contain only one H1 heading.",
#             )
#         )

#         recommendations.append(
#             Recommendation(
#                 title="Keep One H1",
#                 description="Use a single H1 and move others to H2 or H3.",
#             )
#         )

#     @staticmethod
#     def _check_empty_links(
#         content,
#         issues,
#         recommendations,
#     ):

#         for link in content.links:

#             if link.text.strip():
#                 continue

#             issues.append(
#                 Issue(
#                     severity="Low",
#                     title="Empty Anchor Text",
#                     description=f"Link '{link.href}' has no visible text.",
#                 )
#             )

#             recommendations.append(
#                 Recommendation(
#                     title="Add Anchor Text",
#                     description="Provide descriptive anchor text for links.",
#                 )
#             )

#     @staticmethod
#     def _check_missing_image_alt(
#         content,
#         issues,
#         recommendations,
#     ):

#         for image in content.images:

#             if image.alt.strip():
#                 continue

#             issues.append(
#                 Issue(
#                     severity="Medium",
#                     title="Missing Image ALT",
#                     description=f"Image '{image.src}' has no ALT text.",
#                 )
#             )

#             recommendations.append(
#                 Recommendation(
#                     title="Add ALT Text",
#                     description="Every image should have meaningful ALT text.",
#                 )
#             )

#     @staticmethod
#     def _check_missing_image_src(
#         content,
#         issues,
#         recommendations,
#     ):

#         for image in content.images:

#             if image.src.strip():
#                 continue

#             issues.append(
#                 Issue(
#                     severity="High",
#                     title="Missing Image Source",
#                     description="An image tag is missing the src attribute.",
#                 )
#             )

#             recommendations.append(
#                 Recommendation(
#                     title="Provide Image Source",
#                     description="Every image must specify a valid src.",
#                 )
#             )
            
#     @staticmethod
#     def _check_invalid_heading_order(
#         content,
#         issues,
#         recommendations,
#     ):

#         heading_sequence = []

#         for tag in content.soup.find_all(
#             ["h1", "h2", "h3", "h4", "h5", "h6"]
#         ):

#             level = int(tag.name[1])
#             heading_sequence.append(level)

#         previous_level = 0

#         for level in heading_sequence:

#             if previous_level and level > previous_level + 1:

#                 issues.append(
#                     Issue(
#                         severity="Medium",
#                         title="Invalid Heading Order",
#                         description=(
#                             f"Heading level jumps from "
#                             f"H{previous_level} to H{level}."
#                         ),
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Heading Hierarchy",
#                         description=(
#                             "Use sequential heading levels "
#                             "(H1 → H2 → H3)."
#                         ),
#                     )
#                 )

#                 return

#             previous_level = level

#     @staticmethod
#     def _check_duplicate_ids(
#         content,
#         issues,
#         recommendations,
#     ):

#         ids = []

#         for tag in content.soup.find_all(id=True):
#             ids.append(tag["id"])

#         duplicates = {
#             html_id
#             for html_id in ids
#             if ids.count(html_id) > 1
#         }

#         for html_id in duplicates:

#             issues.append(
#                 Issue(
#                     severity="Medium",
#                     title="Duplicate HTML ID",
#                     description=(
#                         f"Duplicate id '{html_id}' found."
#                     ),
#                 )
#             )

#             recommendations.append(
#                 Recommendation(
#                     title="Use Unique IDs",
#                     description=(
#                         "Every HTML id attribute should "
#                         "be unique."
#                     ),
#                 )
#             )

#     @staticmethod
#     def _check_missing_html_attributes(
#         content,
#         issues,
#         recommendations,
#     ):

#         for tag in content.soup.find_all("a"):

#             if not tag.get("href"):

#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Missing href Attribute",
#                         description="Anchor tag missing href.",
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Add href",
#                         description="Every anchor should contain a valid href.",
#                     )
#                 )

#         for tag in content.soup.find_all("img"):

#             if not tag.get("src"):

#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Missing src Attribute",
#                         description="Image missing src attribute.",
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Add Image Source",
#                         description="Every image should specify a src.",
#                     )
#                 )
    
#     @staticmethod
#     def _check_basic_html_validation(
#         content,
#         issues,
#         recommendations,
#     ):

#         required_tags = [
#             "html",
#             "head",
#             "body",
#         ]

#         for tag_name in required_tags:

#             if content.soup.find(tag_name):
#                 continue

#             issues.append(
#                 Issue(
#                     severity="High",
#                     title="Invalid HTML Structure",
#                     description=f"Missing <{tag_name}> tag.",
#                 )
#             )

#             recommendations.append(
#                 Recommendation(
#                     title="Fix HTML Structure",
#                     description=(
#                         f"Add the missing <{tag_name}> element."
#                     ),
#                 )
#             )
    

#     @staticmethod
#     def _check_broken_links(
#         content,
#         issues,
#         recommendations,
#     ):

#         headers = {
#             "User-Agent": "Mozilla/5.0",
#         }

#         timeout = 5

#         for link in content.links:

#             href = link.href.strip()

#             if not href:
#                 continue

#             if href.startswith(("#", "mailto:", "tel:", "javascript:")):
#                 continue

#             absolute_url = urljoin(
#                 content.url,
#                 href,
#             )

#             try:

#                 response = requests.head(
#                     absolute_url,
#                     allow_redirects=True,
#                     timeout=timeout,
#                     headers=headers,
#                 )

#                 if response.status_code >= 400:

#                     issues.append(
#                         Issue(
#                             severity="High",
#                             title="Broken Link",
#                             description=(
#                                 f"'{absolute_url}' returned "
#                                 f"{response.status_code}."
#                             ),
#                         )
#                     )

#                     recommendations.append(
#                         Recommendation(
#                             title="Fix Broken Link",
#                             description=(
#                                 "Update or remove broken hyperlinks."
#                             ),
#                         )
#                     )

#             except requests.RequestException:

#                 issues.append(
#                     Issue(
#                         severity="High",
#                         title="Broken Link",
#                         description=(
#                             f"Unable to access '{absolute_url}'."
#                         ),
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Broken Link",
#                         description=(
#                             "Ensure hyperlinks are reachable."
#                         ),
#                     )
#                 )
    
    
#     @staticmethod
#     def _check_broken_images(
#         content,
#         issues,
#         recommendations,
#     ):

#         headers = {
#             "User-Agent": "Mozilla/5.0",
#         }

#         timeout = 5

#         for image in content.images:

#             src = image.src.strip()

#             if not src:
#                 continue

#             absolute_url = urljoin(
#                 content.url,
#                 src,
#             )

#             try:

#                 response = requests.head(
#                     absolute_url,
#                     allow_redirects=True,
#                     timeout=timeout,
#                     headers=headers,
#                 )

#                 if response.status_code >= 400:

#                     issues.append(
#                         Issue(
#                             severity="Medium",
#                             title="Broken Image",
#                             description=(
#                                 f"'{absolute_url}' returned "
#                                 f"{response.status_code}."
#                             ),
#                         )
#                     )

#                     recommendations.append(
#                         Recommendation(
#                             title="Fix Broken Image",
#                             description=(
#                                 "Replace or repair broken image sources."
#                             ),
#                         )
#                     )

#             except requests.RequestException:

#                 issues.append(
#                     Issue(
#                         severity="Medium",
#                         title="Broken Image",
#                         description=(
#                             f"Unable to access '{absolute_url}'."
#                         ),
#                     )
#                 )

#                 recommendations.append(
#                     Recommendation(
#                         title="Fix Broken Image",
#                         description=(
#                             "Verify image URLs are accessible."
#                         ),
#                     )
#                 )

#     @staticmethod
#     def _calculate_score(issues):

#         score = 100

#         penalties = {
#             "High": 15,
#             "Medium": 8,
#             "Low": 3,
#         }

#         for issue in issues:
#             score -= penalties.get(issue.severity, 0)

#         return max(score, 0)