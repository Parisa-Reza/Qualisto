from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import EvaluationResult, Issue, Recommendation


class SEOQualityEvaluator:
    """
    Evaluates on-page SEO quality using rule-based checks.
    """

    @classmethod
    def evaluate(cls, content: WebsiteContent) -> EvaluationResult:
        issues = []
        recommendations = []

        cls._check_title(content, issues, recommendations)
        cls._check_meta_description(content, issues, recommendations)
        cls._check_content_length(content, issues, recommendations)
        cls._check_paragraph_length(content, issues, recommendations)

        cls._check_internal_link_distribution(content, issues, recommendations)
        cls._check_external_link_distribution(content, issues, recommendations)
        cls._check_image_content_ratio(content, issues, recommendations)
        cls._check_duplicate_headings(content, issues, recommendations)
        cls._check_generic_headings(content, issues, recommendations)
        cls._check_readability(content, issues, recommendations)

        score = cls._calculate_score(issues)

        return EvaluationResult(score=score, issues=issues, recommendations=recommendations)

    @staticmethod
    def _check_title(content, issues, recommendations):
        title = content.title.strip()

        if not title:
            issues.append(Issue(
                severity="High",
                title="Missing SEO Title",
                description="The webpage does not contain a title tag.",
            ))
            recommendations.append(Recommendation(
                title="Add SEO Title",
                description="Provide a unique title between 30 and 60 characters.",
            ))
            return

        if len(title) < 30:
            issues.append(Issue(
                severity="Medium",
                title="Title Too Short",
                description=f"Title contains {len(title)} characters. Recommended length is 30–60 characters.",
            ))
            recommendations.append(Recommendation(
                title="Increase Title Length",
                description="Expand the title while keeping it descriptive.",
            ))

        elif len(title) > 60:
            issues.append(Issue(
                severity="Medium",
                title="Title Too Long",
                description=f"Title contains {len(title)} characters. Recommended length is 30–60 characters.",
            ))
            recommendations.append(Recommendation(
                title="Reduce Title Length",
                description="Keep the title under 60 characters.",
            ))
 
    
    @staticmethod
    def _check_meta_description(content, issues, recommendations):

        description = content.meta_description.strip()

        if not description:
            issues.append(Issue(
                severity="High",
                title="Missing Meta Description",
                description="The webpage does not contain a meta description.",
            ))

            recommendations.append(Recommendation(
                title="Add Meta Description",
                description="Provide a unique meta description between 120 and 160 characters.",
            ))
            return

        if len(description) < 120:
            issues.append(Issue(
                severity="Medium",
                title="Meta Description Too Short",
                description=f"Meta description contains {len(description)} characters. Recommended length is 120–160 characters.",
            ))

            recommendations.append(Recommendation(
                title="Increase Meta Description Length",
                description="Expand the meta description while keeping it relevant.",
            ))

        elif len(description) > 160:
            issues.append(Issue(
                severity="Medium",
                title="Meta Description Too Long",
                description=f"Meta description contains {len(description)} characters. Recommended length is 120–160 characters.",
            ))

            recommendations.append(Recommendation(
                title="Reduce Meta Description Length",
                description="Keep the meta description below 160 characters.",
            ))

    @staticmethod
    def _check_content_length(content, issues, recommendations):

        word_count = len(content.plain_text.split())

        if word_count < 300:

            issues.append(Issue(
                severity="High",
                title="Thin Content",
                description=f"The page contains only {word_count} words. Pages should contain at least 300 words.",
            ))

            recommendations.append(Recommendation(
                title="Increase Content Length",
                description="Expand the content to provide sufficient information and improve topical coverage.",
            ))

        elif word_count < 600:

            issues.append(Issue(
                severity="Medium",
                title="Low Content Coverage",
                description=f"The page contains {word_count} words. More comprehensive content is recommended for better SEO performance.",
            ))

            recommendations.append(Recommendation(
                title="Expand Content Coverage",
                description="Add more valuable and relevant information to cover the topic more comprehensively.",
            ))

        elif word_count <= 2500:
            return

        elif word_count <= 4000:

            issues.append(Issue(
                severity="Low",
                title="Very Long Content",
                description=f"The page contains {word_count} words. Ensure the content remains well-structured and easy to navigate.",
            ))

            recommendations.append(Recommendation(
                title="Improve Content Structure",
                description="Use clear headings, shorter paragraphs, and a table of contents if appropriate.",
            ))

        else:

            issues.append(Issue(
                severity="Medium",
                title="Excessively Long Content",
                description=f"The page contains {word_count} words, which may overwhelm readers and affect usability.",
            ))

            recommendations.append(Recommendation(
                title="Split or Reorganize Content",
                description="Consider dividing the content into multiple pages or sections while preserving a logical site structure.",
            ))


    @staticmethod
    def _check_paragraph_length(content, issues, recommendations):

        long_paragraphs = 0

        for paragraph in content.paragraphs:

            words = len(paragraph.split())

            if words > 180:
                long_paragraphs += 1

        if long_paragraphs:

            issues.append(Issue(
                severity="Low",
                title="Long Paragraphs",
                description=f"{long_paragraphs} paragraph(s) exceed 180 words.",
            ))

            recommendations.append(Recommendation(
                title="Split Long Paragraphs",
                description="Break long paragraphs into smaller sections for better readability.",
            ))



    @staticmethod
    def _check_internal_link_distribution(content, issues, recommendations):

        word_count = len(content.plain_text.split())

        internal_links = [
            link for link in content.links
            if link.href.startswith("/")
        ]

        expected = max(1, word_count // 500)

        if len(internal_links) < expected:

            issues.append(Issue(
                severity="Low",
                title="Low Internal Linking",
                description=f"Only {len(internal_links)} internal link(s) found for {word_count} words.",
            ))

            recommendations.append(Recommendation(
                title="Add Internal Links",
                description="Link to other relevant pages to improve navigation and SEO.",
            ))


    @staticmethod
    def _check_external_link_distribution(content, issues, recommendations):

        external_links = [
            link for link in content.links
            if link.href.startswith("http")
        ]

        if len(external_links) > 25:

            issues.append(Issue(
                severity="Low",
                title="Too Many External Links",
                description=f"The page contains {len(external_links)} external links.",
            ))

            recommendations.append(Recommendation(
                title="Reduce External Links",
                description="Use external links only when they add value.",
            ))


    @staticmethod
    def _check_image_content_ratio(content, issues, recommendations):

        words = len(content.plain_text.split())

        expected_images = max(1, words // 800)

        if len(content.images) < expected_images:

            issues.append(Issue(
                severity="Low",
                title="Low Image Coverage",
                description=f"The page contains {words} words but only {len(content.images)} image(s).",
            ))

            recommendations.append(Recommendation(
                title="Add Relevant Images",
                description="Include images to improve user engagement.",
            ))

    @staticmethod
    def _check_duplicate_headings(content, issues, recommendations):

        headings = (
            content.headings.h1 +
            content.headings.h2 +
            content.headings.h3 +
            content.headings.h4 +
            content.headings.h5 +
            content.headings.h6
        )

        duplicates = {
            heading
            for heading in headings
            if headings.count(heading) > 1
        }

        if duplicates:

            issues.append(Issue(
                severity="Low",
                title="Duplicate Headings",
                description="Some headings are repeated.",
            ))

            recommendations.append(Recommendation(
                title="Use Unique Headings",
                description="Give each section a unique heading.",
            ))



    @staticmethod
    def _check_generic_headings(content, issues, recommendations):

        generic = {
            "home",
            "about",
            "page",
            "section",
            "article",
            "content",
            "welcome",
            "services",
        }

        headings = (
            content.headings.h1 +
            content.headings.h2 +
            content.headings.h3 +
            content.headings.h4 +
            content.headings.h5 +
            content.headings.h6
        )

        found = [
            heading
            for heading in headings
            if heading.strip().lower() in generic
        ]

        if found:

            issues.append(Issue(
                severity="Low",
                title="Generic Headings",
                description=f"Found generic headings: {', '.join(found)}.",
            ))

            recommendations.append(Recommendation(
                title="Use Descriptive Headings",
                description="Replace generic headings with topic-specific ones.",
            ))
    @staticmethod
    def _check_readability(content, issues, recommendations):

        sentences = [
            s.strip()
            for s in content.plain_text.replace("!", ".").replace("?", ".").split(".")
            if s.strip()
        ]

        if not sentences:
            return

        words = len(content.plain_text.split())

        avg = words / len(sentences)

        if avg > 25:

            issues.append(Issue(
                severity="Low",
                title="Low Readability",
                description=f"Average sentence length is {avg:.1f} words.",
            ))

            recommendations.append(Recommendation(
                title="Improve Readability",
                description="Use shorter sentences to improve readability.",
            ))




    @staticmethod
    def _calculate_score(issues):
        score = 100
        penalties = {"High": 15, "Medium": 8, "Low": 3}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(score, 0)