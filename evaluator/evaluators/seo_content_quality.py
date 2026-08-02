import re
from evaluator.extractor.schemas import WebsiteContent
from evaluator.evaluators.schemas import EvaluationResult, Issue, Recommendation


class SEOQualityEvaluator:
    """
    Evaluates on-page SEO quality using rule-based checks.
    """

    @classmethod
    def evaluate(cls, content: WebsiteContent, user_prompt: str = "") -> EvaluationResult:
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

        target_keywords = cls._extract_keywords(user_prompt)
        cls._check_keyword_presence(content, target_keywords, issues, recommendations)
        cls._check_keyword_density(content, target_keywords, issues, recommendations)

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
        internal_links = [link for link in content.links if link.href.startswith("/")]
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
        external_links = [link for link in content.links if link.href.startswith("http")]

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
        duplicates = {heading for heading in headings if headings.count(heading) > 1}

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
            "home", "about", "page", "section", "article",
            "content", "welcome", "services",
        }
        headings = (
            content.headings.h1 +
            content.headings.h2 +
            content.headings.h3 +
            content.headings.h4 +
            content.headings.h5 +
            content.headings.h6
        )
        found = [heading for heading in headings if heading.strip().lower() in generic]

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
    def _extract_keywords(user_prompt: str) -> list[str]:
        """
        Extract target keywords/phrases from the user prompt.

        This is a deterministic first-pass extractor.

        It produces:
            - meaningful single words
            - meaningful two-word phrases
            - meaningful three-word phrases

        The extracted keywords are later checked against:
            title , meta description , H1 , H2 , H3 , body content
        """
        if not user_prompt.strip():
            return []

        text = user_prompt.lower()
        # Replace punctuation with spaces.
        text = re.sub(r"[^\w\s'-]", " ", text)
        # Normalize whitespace.
        words = text.split()
        if not words:
            return []

        stop_words = {
            "a", "an", "and", "are", "be", "by", "for", "from", "has",
            "have", "in", "is", "it", "of", "on", "or", "the", "this",
            "to", "with", "about", "create", "make", "build", "write",
            "page", "website", "webpage", "include", "provide", "using",
            "should", "must",
        }

        keywords = []

        # Single-word keywords
        for word in words:
            if len(word) >= 3 and word not in stop_words and word not in keywords:
                keywords.append(word)

        # Two-word phrases Example: "Bali beaches" , "Bali hotels"
        for index in range(len(words) - 1):
            first = words[index]
            second = words[index + 1]
            if first in stop_words or second in stop_words:
                continue
            phrase = f"{first} {second}"
            if phrase not in keywords:
                keywords.append(phrase)

        # Three-word phrases
        for index in range(len(words) - 2):
            phrase_words = words[index:index + 3]
            meaningful_words = [word for word in phrase_words if word not in stop_words]
            # Require at least two meaningful words.
            if len(meaningful_words) < 2:
                continue
            phrase = " ".join(phrase_words)
            if phrase not in keywords:
                keywords.append(phrase)

        return keywords

    # KEYWORD PRESENCE / PLACEMENT
    @staticmethod
    def _check_keyword_presence(content, target_keywords, issues, recommendations):
        """
        Checks whether prompt-derived keywords appear in important SEO/content locations.

        Locations checked: , Title , Meta description , H1 , H2 , H3 , Body content

        This does NOT require every keyword to appear in every location.

        A keyword is considered sufficiently represented if it appears somewhere in the webpage.

        Missing from the entire webpage: High severity

        Present only in body:
            Low severity recommendation to consider using it
            in an important heading/title location.
        """
        if not target_keywords:
            return

        title = (content.title or "").lower()
        meta = (content.meta_description or "").lower()
        h1 = " ".join(content.headings.h1).lower()
        h2 = " ".join(content.headings.h2).lower()
        h3 = " ".join(content.headings.h3).lower()
        body = (content.plain_text or "").lower()

        for keyword in target_keywords:
            keyword = keyword.strip().lower()
            if not keyword:
                continue

            # Check each webpage location.
            in_title = keyword in title
            in_meta = keyword in meta
            in_h1 = keyword in h1
            in_h2 = keyword in h2
            in_h3 = keyword in h3
            in_body = keyword in body

            # Keyword does not appear anywhere.
            if not any((in_title, in_meta, in_h1, in_h2, in_h3, in_body)):
                issues.append(
                    Issue(
                        severity="High",
                        title="Missing Target Keyword",
                        description=(
                            f'The target keyword "{keyword}" from the user prompt '
                            "does not appear in the webpage content."
                        ),
                    )
                )
                recommendations.append(
                    Recommendation(
                        title="Add Target Keyword",
                        description=f'Consider naturally covering "{keyword}" in relevant webpage content.',
                    )
                )
                continue

            # Keyword exists only in body.
            if in_body and not any((in_title, in_h1, in_h2, in_h3)):
                issues.append(
                    Issue(
                        severity="Low",
                        title="Weak Keyword Placement",
                        description=(
                            f'The target keyword "{keyword}" appears in body content '
                            "but not in the title, meta description, H1, H2, or H3."
                        ),
                    )
                )
                recommendations.append(
                    Recommendation(
                        title="Improve Keyword Placement",
                        description=(
                            f'Consider naturally including "{keyword}" in an '
                            "appropriate title or heading where relevant."
                        ),
                    )
                )

    @staticmethod
    def _check_keyword_density(content, target_keywords, issues, recommendations):
        """
        Check density of explicitly supplied target keywords.

        Rules:
            0 occurrences       -> Missing Target Keyword
            < 0.5%              -> Low Keyword Density
            0.5% - 2.0%         -> Acceptable
            > 2.0%              -> High Keyword Density

        Keyword matching is:
            - case-insensitive
            - whitespace-normalized
            - supports single-word keywords
            - supports multi-word keywords
        """
        text = content.plain_text.strip()
        if not text or not target_keywords:
            return

        normalized_text = text.lower()
        # Tokenize the complete page once.
        words = re.findall(r"\b[\w'-]+\b", normalized_text)
        if not words:
            return

        word_count = len(words)

        for keyword in target_keywords:
            keyword = keyword.strip().lower()
            if not keyword:
                continue

            keyword_words = re.findall(r"\b[\w'-]+\b", keyword)
            if not keyword_words:
                continue

            # Supports: "bali" , "bali travel" , "travel guide bali"
            pattern = r"\b" + r"\s+".join(re.escape(word) for word in keyword_words) + r"\b"
            occurrences = len(re.findall(pattern, normalized_text))


            # Explicitly distinguish a missing keyword from a keyword that merely has low density.

            if occurrences == 0:
                issues.append(
                    Issue(
                        severity="Medium",
                        title="Missing Target Keyword",
                        description=f'The target keyword "{keyword}" does not appear in the page content.',
                    )
                )
                recommendations.append(
                    Recommendation(
                        title="Add Target Keyword",
                        description=f'Use the target keyword "{keyword}" naturally in relevant page content.',
                    )
                )
                continue

            density = (occurrences / word_count) * 100

            # LOW DENSITY

            if density < 0.5:
                issues.append(
                    Issue(
                        severity="Low",
                        title="Low Keyword Density",
                        description=(
                            f'The target keyword "{keyword}" appears {occurrences} time(s), '
                            f"resulting in {density:.2f}% keyword density."
                        ),
                    )
                )
                recommendations.append(
                    Recommendation(
                        title="Improve Keyword Usage",
                        description=f'Use "{keyword}" naturally where it is relevant to the topic.',
                    )
                )

            # HIGH DENSITY

            elif density > 2.0:
                issues.append(
                    Issue(
                        severity="Medium",
                        title="High Keyword Density",
                        description=(
                            f'The target keyword "{keyword}" appears {occurrences} time(s), '
                            f"resulting in {density:.2f}% keyword density."
                        ),
                    )
                )
                recommendations.append(
                    Recommendation(
                        title="Reduce Keyword Repetition",
                        description=(
                            f'Reduce repeated use of "{keyword}" and use natural '
                            "variations where appropriate."
                        ),
                    )
                )

    @staticmethod
    def _calculate_score(issues):
        score = 100
        penalties = {"High": 15, "Medium": 8, "Low": 3}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(score, 0)