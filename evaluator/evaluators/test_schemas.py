from django.test import SimpleTestCase

from evaluator.evaluators.schemas import (
    EvaluationResult,
    Issue,
    Recommendation,
)


class EvaluatorSchemasTest(SimpleTestCase):

    def test_issue_schema(self):

        issue = Issue(
            severity="High",
            title="Missing Title",
            description="The page does not contain a title tag.",
        )

        self.assertEqual(issue.severity, "High")
        self.assertEqual(issue.title, "Missing Title")
        self.assertEqual(
            issue.description,
            "The page does not contain a title tag.",
        )

    def test_recommendation_schema(self):

        recommendation = Recommendation(
            title="Add Title",
            description="Include a meaningful HTML title.",
        )

        self.assertEqual(
            recommendation.title,
            "Add Title",
        )

        self.assertEqual(
            recommendation.description,
            "Include a meaningful HTML title.",
        )

    def test_evaluation_result_schema(self):

        result = EvaluationResult(
            score=90,
            issues=[
                Issue(
                    severity="Medium",
                    title="Missing Meta Description",
                    description="Meta description not found.",
                ),
                Issue(
                    severity="Low",
                    title="Empty Anchor Text",
                    description="Anchor has no visible text.",
                ),
            ],
            recommendations=[
                Recommendation(
                    title="Add Meta Description",
                    description="Provide a descriptive meta tag.",
                ),
                Recommendation(
                    title="Add Anchor Text",
                    description="Provide descriptive text for links.",
                ),
            ],
        )

        self.assertEqual(result.score, 90)

        self.assertEqual(len(result.issues), 2)

        self.assertEqual(len(result.recommendations), 2)

        self.assertEqual(
            result.issues[0].title,
            "Missing Meta Description",
        )

        self.assertEqual(
            result.issues[1].title,
            "Empty Anchor Text",
        )

        self.assertEqual(
            result.recommendations[0].title,
            "Add Meta Description",
        )

        self.assertEqual(
            result.recommendations[1].title,
            "Add Anchor Text",
        )

    def test_empty_result(self):

        result = EvaluationResult(score=100)

        self.assertEqual(result.score, 100)
        self.assertEqual(result.issues, [])
        self.assertEqual(result.recommendations, [])

    def test_multiple_issue_severities(self):

        result = EvaluationResult(
            score=65,
            issues=[
                Issue(
                    severity="High",
                    title="Broken Link",
                    description="A link returned 404.",
                ),
                Issue(
                    severity="Medium",
                    title="Duplicate ID",
                    description="Duplicate HTML id found.",
                ),
                Issue(
                    severity="Low",
                    title="Empty Heading",
                    description="Heading contains no text.",
                ),
            ],
        )

        self.assertEqual(len(result.issues), 3)

        self.assertEqual(
            result.issues[0].severity,
            "High",
        )

        self.assertEqual(
            result.issues[1].severity,
            "Medium",
        )

        self.assertEqual(
            result.issues[2].severity,
            "Low",
        )

    def test_multiple_recommendations(self):

        result = EvaluationResult(
            score=80,
            recommendations=[
                Recommendation(
                    title="Fix Broken Link",
                    description="Update or remove broken hyperlinks.",
                ),
                Recommendation(
                    title="Add ALT Text",
                    description="Provide descriptive ALT text for images.",
                ),
            ],
        )

        self.assertEqual(
            len(result.recommendations),
            2,
        )

        self.assertEqual(
            result.recommendations[0].title,
            "Fix Broken Link",
        )

        self.assertEqual(
            result.recommendations[1].title,
            "Add ALT Text",
        )