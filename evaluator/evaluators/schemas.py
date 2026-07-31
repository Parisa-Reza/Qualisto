from dataclasses import dataclass, field


@dataclass(slots=True)
class Issue:
    """
    Represents a single issue found during evaluation.
    """

    severity: str
    title: str
    description: str


@dataclass(slots=True)
class Recommendation:
    """
    Represents a recommendation for improving the webpage.
    """

    title: str
    description: str


@dataclass(slots=True)
class EvaluationResult:
    """
    Standard output returned by every evaluator.
    """

    score: int

    issues: list[Issue] = field(default_factory=list)

    recommendations: list[Recommendation] = field(default_factory=list)


@dataclass(slots=True)
class PromptAlignmentResult(EvaluationResult):
    missing_requirements: list[str] = field(default_factory=list)
    off_topic_sections: list[str] = field(default_factory=list)

@dataclass(slots=True)
class KnowledgeValidationResult(EvaluationResult):
    verified_claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    uncertain_claims: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchQualityResult(EvaluationResult):
    """
    Evaluates whether webpage content is useful and satisfying
    for a user searching for the page's topic.

    This is content/search-quality evaluation, not a direct
    Google ranking prediction.
    """

    search_intent: str = ""
    helpfulness_score: int = 0
    completeness_score: int = 0
    natural_writing_score: int = 0
    repetition_score: int = 0
    ai_sounding_score: int = 0
    content_depth_score: int = 0
    readability_score: int = 0
    user_satisfaction_score: int = 0
    missing_sections: list[str] = field(default_factory=list)