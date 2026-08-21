const form = document.getElementById("evaluation-form");
const urlInput = document.getElementById("website-url");
const promptInput = document.getElementById("user-prompt");
const evaluateButton = document.getElementById("evaluate-button");
const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");
const report = document.getElementById("report");
const overallScore = document.getElementById("overall-score");
const reportUrl = document.getElementById("report-url");
const reportPrompt = document.getElementById("report-prompt");
const scoreGrid = document.getElementById("score-grid");
const moduleTabs = document.getElementById("module-tabs");
const activeModule = document.getElementById("active-module");

const MODULE_ORDER = [
  "prompt_alignment",
  "knowledge_validation",
  "search_quality",
  "technical_html",
  "seo_quality",
];

function getCSRFToken() {
  const token = document.querySelector("[name=csrfmiddlewaretoken]");
  return token ? token.value : "";
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
      headers: { "X-CSRFToken": getCSRFToken() },
      body: new URLSearchParams({ url: url, prompt: userPrompt }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Evaluation failed.");
    }
    renderReport(data.report);
  } catch (error) {
    showError(error.message || "Evaluation failed.");
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
  renderRequestSummary(data);
  renderModuleScores(data.modules);
  renderModuleTabs(data.modules);
  activateModule("prompt_alignment", data.modules);
}

function renderOverallScore(data) {
  const score = data.final_score ?? 0;
  overallScore.textContent = `${score}/100`;
}

function renderRequestSummary(data) {
  reportUrl.textContent = data.url || "-";
  reportPrompt.textContent = data.user_prompt || "-";
}

function renderModuleScores(modules) {
  scoreGrid.innerHTML = "";
  MODULE_ORDER.forEach((moduleKey) => {
    const module = modules[moduleKey];
    if (!module) return;

    const item = document.createElement("div");
    item.className = "score-item";

    const title = document.createElement("h3");
    title.textContent = module.name;

    const value = document.createElement("div");
    value.className = "score-value";
    value.textContent = `${module.score}/100`;

    item.appendChild(title);
    item.appendChild(value);
    scoreGrid.appendChild(item);
  });
}

function renderModuleTabs(modules) {
  moduleTabs.innerHTML = "";
  MODULE_ORDER.forEach((moduleKey) => {
    const module = modules[moduleKey];
    if (!module) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "module-tab";
    button.dataset.module = moduleKey;
    button.textContent = module.name;
    button.addEventListener("click", function () {
      activateModule(moduleKey, modules);
    });
    moduleTabs.appendChild(button);
  });
}

function activateModule(moduleKey, modules) {
  const module = modules[moduleKey];
  if (!module) return;

  const tabs = document.querySelectorAll(".module-tab");
  tabs.forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.module === moduleKey);
  });
  renderActiveModule(module);
}

function renderActiveModule(module) {
  activeModule.innerHTML = "";

  const header = document.createElement("div");
  header.className = "active-module-header";

  const title = document.createElement("h2");
  title.className = "active-module-title";
  title.textContent = module.name;

  const score = document.createElement("div");
  score.className = "active-module-score";
  score.textContent = `${module.score}/100`;

  header.appendChild(title);
  header.appendChild(score);
  activeModule.appendChild(header);

  const issuesSection = document.createElement("div");
  issuesSection.className = "module-section";

  const issuesTitle = document.createElement("h3");
  issuesTitle.className = "module-section-title";
  issuesTitle.textContent = `Issues ${module.issues.length}`;
  issuesSection.appendChild(issuesTitle);

  if (module.issues.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No issues found.";
    issuesSection.appendChild(empty);
  } else {
    module.issues.forEach((issue) => {
      issuesSection.appendChild(createIssueCard(issue));
    });
  }
  activeModule.appendChild(issuesSection);

  const recommendationsSection = document.createElement("div");
  recommendationsSection.className = "module-section";

  const recommendationsTitle = document.createElement("h3");
  recommendationsTitle.className = "module-section-title";
  recommendationsTitle.textContent = "Recommendations";
  recommendationsSection.appendChild(recommendationsTitle);

  if (module.recommendations.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No recommendations.";
    recommendationsSection.appendChild(empty);
  } else {
    module.recommendations.forEach((recommendation) => {
      recommendationsSection.appendChild(createRecommendationCard(recommendation));
    });
  }
  activeModule.appendChild(recommendationsSection);
}

function createIssueCard(issue) {
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
  return container;
}

function createRecommendationCard(recommendation) {
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
  return container;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}
