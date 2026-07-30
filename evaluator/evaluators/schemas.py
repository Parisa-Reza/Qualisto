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