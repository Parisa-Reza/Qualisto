const form = document.getElementById("evaluation-form");

const urlInput = document.getElementById("website-url");
const promptInput = document.getElementById("user-prompt");

const evaluateButton = document.getElementById("evaluate-button");

const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");

const report = document.getElementById("report");

const overallScore = document.getElementById("overall-score");
const scoreStatus = document.getElementById("score-status");

const scoreGrid = document.getElementById("score-grid");
const issuesContainer = document.getElementById("issues");
const recommendationsContainer = document.getElementById("recommendations");

function getCSRFToken() {
    return document.querySelector(
        "[name=csrfmiddlewaretoken]"
    ).value;
}

form.addEventListener("submit", async function (event) {
  event.preventDefault();

  clearError();

  const url = urlInput.value.trim();
  const userPrompt = promptInput.value.trim();

  if (!url || !userPrompt) {
    showError("URL and user prompt are required.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch("/api/evaluate/", {
      method: "POST",

      headers: {
        "X-CSRFToken": getCSRFToken(),
      },

      body: new URLSearchParams({
        url: url,
        prompt: userPrompt,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || data.error || "Evaluation failed.");
    }

    renderReport(data.report);
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  evaluateButton.disabled = isLoading;

  if (isLoading) {
    loading.classList.remove("hidden");

    report.classList.add("hidden");

    evaluateButton.textContent = "Evaluating...";
  } else {
    loading.classList.add("hidden");

    evaluateButton.textContent = "Evaluate Website";
  }
}

function renderReport(data) {
  report.classList.remove("hidden");

  renderOverallScore(data);

  renderScores(data);

  renderIssues(data);

  renderRecommendations(data);
}

function renderOverallScore(data) {
  const score = data.final_score ?? data.overall_score ?? data.score ?? 0;

  overallScore.textContent = `${score}/100`;

  if (score >= 80) {
    scoreStatus.textContent = "Good quality";
  } else if (score >= 60) {
    scoreStatus.textContent = "Needs improvement";
  } else {
    scoreStatus.textContent = "Significant improvements required";
  }
}

function renderScores(data) {
  scoreGrid.innerHTML = "";

  const scores =
    data.scores ||
    data.category_scores ||
    {
      prompt_alignment: data.prompt_alignment,
      knowledge_validation: data.knowledge_validation,
      seo_quality: data.seo_quality,
      search_quality: data.search_quality,
      technical_html: data.technical_html,
    };

  Object.entries(scores).forEach(([name, score]) => {
    const item = document.createElement("div");

    item.className = "score-item";

    const title = document.createElement("h3");

    title.textContent = formatName(name);

    const value = document.createElement("div");

    value.className = "score-value";

    value.textContent = `${score}/100`;

    item.appendChild(title);
    item.appendChild(value);

    scoreGrid.appendChild(item);
  });
}

function renderIssues(data) {
  issuesContainer.innerHTML = "";

  const issues = data.issues || [];

  if (issues.length === 0) {
    issuesContainer.textContent = "No issues found.";

    return;
  }

  issues.forEach((issue) => {
    const container = document.createElement("div");

    container.className = "issue";

    const title = document.createElement("div");

    title.className = "issue-title";

    title.textContent = issue.title || "Issue";

    const description = document.createElement("div");

    description.className = "issue-description";

    description.textContent = issue.description || "";

    container.appendChild(title);

    container.appendChild(description);

    issuesContainer.appendChild(container);
  });
}

function renderRecommendations(data) {
  recommendationsContainer.innerHTML = "";

  const recommendations = data.recommendations || [];

  if (recommendations.length === 0) {
    recommendationsContainer.textContent = "No recommendations.";

    return;
  }

  recommendations.forEach((recommendation) => {
    const container = document.createElement("div");

    container.className = "recommendation";

    const title = document.createElement("div");

    title.className = "recommendation-title";

    title.textContent = recommendation.title || "Recommendation";

    const description = document.createElement("div");

    description.className = "recommendation-description";

    description.textContent = recommendation.description || "";

    container.appendChild(title);

    container.appendChild(description);

    recommendationsContainer.appendChild(container);
  });
}

function formatName(name) {
  return name
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function showError(message) {
  errorBox.textContent = message;

  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";

  errorBox.classList.add("hidden");
}
