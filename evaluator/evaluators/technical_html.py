from urllib.parse import urljoin
import requests

from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    Recommendation,
)


class TechnicalHTMLEvaluator:
    """
    Evaluates the technical HTML quality of a webpage.
    """

    @classmethod
    def evaluate(cls, content: WebsiteContent) -> EvaluationResult:

        issues = []
        recommendations = []

        cls._check_title(
            content,
            issues,
            recommendations,
        )

        cls._check_meta_description(
            content,
            issues,
            recommendations,
        )

        cls._check_duplicate_h1(
            content,
            issues,
            recommendations,
        )

        cls._check_empty_links(
            content,
            issues,
            recommendations,
        )

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

        cls._check_invalid_heading_order(
            content,
            issues,
            recommendations,
        )

        cls._check_duplicate_ids(
            content,
            issues,
            recommendations,
        )

        cls._check_missing_html_attributes(
            content,
            issues,
            recommendations,
        )

        cls._check_basic_html_validation(
            content,
            issues,
            recommendations,
        )

        cls._check_broken_links(
            content,
            issues,
            recommendations,
        )

        cls._check_broken_images(
            content,
            issues,
            recommendations,
        )

        score = cls._calculate_score(issues)

        return EvaluationResult(
            score=score,
            issues=issues,
            recommendations=recommendations,
        )

    @staticmethod
    def _check_title(
        content,
        issues,
        recommendations,
    ):

        if content.title:
            return

        issues.append(
            Issue(
                severity="High",
                title="Missing HTML Title",
                description="The webpage does not contain a title tag.",
            )
        )

        recommendations.append(
            Recommendation(
                title="Add HTML Title",
                description="Add a descriptive and unique HTML title.",
            )
        )

    @staticmethod
    def _check_meta_description(
        content,
        issues,
        recommendations,
    ):

        if content.meta_description:
            return

        issues.append(
            Issue(
                severity="Medium",
                title="Missing Meta Description",
                description="No meta description was found.",
            )
        )

        recommendations.append(
            Recommendation(
                title="Add Meta Description",
                description="Provide a meaningful meta description.",
            )
        )

    @staticmethod
    def _check_duplicate_h1(
        content,
        issues,
        recommendations,
    ):

        if len(content.headings.h1) <= 1:
            return

        issues.append(
            Issue(
                severity="Medium",
                title="Multiple H1 Tags",
                description="A webpage should contain only one H1 heading.",
            )
        )

        recommendations.append(
            Recommendation(
                title="Keep One H1",
                description="Use a single H1 and move others to H2 or H3.",
            )
        )

    @staticmethod
    def _check_empty_links(
        content,
        issues,
        recommendations,
    ):

        for link in content.links:

            if link.text.strip():
                continue

            issues.append(
                Issue(
                    severity="Low",
                    title="Empty Anchor Text",
                    description=f"Link '{link.href}' has no visible text.",
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add Anchor Text",
                    description="Provide descriptive anchor text for links.",
                )
            )

    @staticmethod
    def _check_missing_image_alt(
        content,
        issues,
        recommendations,
    ):

        for image in content.images:

            if image.alt.strip():
                continue

            issues.append(
                Issue(
                    severity="Medium",
                    title="Missing Image ALT",
                    description=f"Image '{image.src}' has no ALT text.",
                )
            )

            recommendations.append(
                Recommendation(
                    title="Add ALT Text",
                    description="Every image should have meaningful ALT text.",
                )
            )

    @staticmethod
    def _check_missing_image_src(
        content,
        issues,
        recommendations,
    ):

        for image in content.images:

            if image.src.strip():
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Missing Image Source",
                    description="An image tag is missing the src attribute.",
                )
            )

            recommendations.append(
                Recommendation(
                    title="Provide Image Source",
                    description="Every image must specify a valid src.",
                )
            )
            
    @staticmethod
    def _check_invalid_heading_order(
        content,
        issues,
        recommendations,
    ):

        heading_sequence = []

        for tag in content.soup.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6"]
        ):

            level = int(tag.name[1])
            heading_sequence.append(level)

        previous_level = 0

        for level in heading_sequence:

            if previous_level and level > previous_level + 1:

                issues.append(
                    Issue(
                        severity="Medium",
                        title="Invalid Heading Order",
                        description=(
                            f"Heading level jumps from "
                            f"H{previous_level} to H{level}."
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Heading Hierarchy",
                        description=(
                            "Use sequential heading levels "
                            "(H1 → H2 → H3)."
                        ),
                    )
                )

                return

            previous_level = level

    @staticmethod
    def _check_duplicate_ids(
        content,
        issues,
        recommendations,
    ):

        ids = []

        for tag in content.soup.find_all(id=True):
            ids.append(tag["id"])

        duplicates = {
            html_id
            for html_id in ids
            if ids.count(html_id) > 1
        }

        for html_id in duplicates:

            issues.append(
                Issue(
                    severity="Medium",
                    title="Duplicate HTML ID",
                    description=(
                        f"Duplicate id '{html_id}' found."
                    ),
                )
            )

            recommendations.append(
                Recommendation(
                    title="Use Unique IDs",
                    description=(
                        "Every HTML id attribute should "
                        "be unique."
                    ),
                )
            )

    @staticmethod
    def _check_missing_html_attributes(
        content,
        issues,
        recommendations,
    ):

        for tag in content.soup.find_all("a"):

            if not tag.get("href"):

                issues.append(
                    Issue(
                        severity="High",
                        title="Missing href Attribute",
                        description="Anchor tag missing href.",
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Add href",
                        description="Every anchor should contain a valid href.",
                    )
                )

        for tag in content.soup.find_all("img"):

            if not tag.get("src"):

                issues.append(
                    Issue(
                        severity="High",
                        title="Missing src Attribute",
                        description="Image missing src attribute.",
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Add Image Source",
                        description="Every image should specify a src.",
                    )
                )
    
    @staticmethod
    def _check_basic_html_validation(
        content,
        issues,
        recommendations,
    ):

        required_tags = [
            "html",
            "head",
            "body",
        ]

        for tag_name in required_tags:

            if content.soup.find(tag_name):
                continue

            issues.append(
                Issue(
                    severity="High",
                    title="Invalid HTML Structure",
                    description=f"Missing <{tag_name}> tag.",
                )
            )

            recommendations.append(
                Recommendation(
                    title="Fix HTML Structure",
                    description=(
                        f"Add the missing <{tag_name}> element."
                    ),
                )
            )
    

    @staticmethod
    def _check_broken_links(
        content,
        issues,
        recommendations,
    ):

        headers = {
            "User-Agent": "Mozilla/5.0",
        }

        timeout = 5

        for link in content.links:

            href = link.href.strip()

            if not href:
                continue

            if href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue

            absolute_url = urljoin(
                content.url,
                href,
            )

            try:

                response = requests.head(
                    absolute_url,
                    allow_redirects=True,
                    timeout=timeout,
                    headers=headers,
                )

                if response.status_code >= 400:

                    issues.append(
                        Issue(
                            severity="High",
                            title="Broken Link",
                            description=(
                                f"'{absolute_url}' returned "
                                f"{response.status_code}."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Link",
                            description=(
                                "Update or remove broken hyperlinks."
                            ),
                        )
                    )

            except requests.RequestException:

                issues.append(
                    Issue(
                        severity="High",
                        title="Broken Link",
                        description=(
                            f"Unable to access '{absolute_url}'."
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Broken Link",
                        description=(
                            "Ensure hyperlinks are reachable."
                        ),
                    )
                )
    
    
    @staticmethod
    def _check_broken_images(
        content,
        issues,
        recommendations,
    ):

        headers = {
            "User-Agent": "Mozilla/5.0",
        }

        timeout = 5

        for image in content.images:

            src = image.src.strip()

            if not src:
                continue

            absolute_url = urljoin(
                content.url,
                src,
            )

            try:

                response = requests.head(
                    absolute_url,
                    allow_redirects=True,
                    timeout=timeout,
                    headers=headers,
                )

                if response.status_code >= 400:

                    issues.append(
                        Issue(
                            severity="Medium",
                            title="Broken Image",
                            description=(
                                f"'{absolute_url}' returned "
                                f"{response.status_code}."
                            ),
                        )
                    )

                    recommendations.append(
                        Recommendation(
                            title="Fix Broken Image",
                            description=(
                                "Replace or repair broken image sources."
                            ),
                        )
                    )

            except requests.RequestException:

                issues.append(
                    Issue(
                        severity="Medium",
                        title="Broken Image",
                        description=(
                            f"Unable to access '{absolute_url}'."
                        ),
                    )
                )

                recommendations.append(
                    Recommendation(
                        title="Fix Broken Image",
                        description=(
                            "Verify image URLs are accessible."
                        ),
                    )
                )

    @staticmethod
    def _calculate_score(issues):

        score = 100

        penalties = {
            "High": 15,
            "Medium": 8,
            "Low": 3,
        }

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(score, 0)