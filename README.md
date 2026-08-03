# Qualisto

## Description

Qualisto is an AI powered engine that evaluates AI-generated webpage content based on prompt alignment, SEO content quality, technical health, search quality, and factual correctness.

You give it a prompt (whatever the page was supposed to accomplish) and a URL. Qualisto fetches that page, pulls out its text, HTML and metadata, then runs it through five separate evaluation modules. Each module scores the page on a different dimension: does it match the original prompt, are the facts on it actually true, is the SEO solid, would a search engine visitor be satisfied, and is the HTML technically sound. Those scores eventually get combined into one report with an overall grade and a list of things to fix.

## Workflow



The flow works like this:

1. A user submits a prompt describing what the page was meant to do, along with the website URL to check.
2. Qualisto fetches the raw HTML and parses it.
3. Text, headings, paragraphs, links, images, metadata and property cards get pulled out into a structured object.
4. That structured content is handed to a LangGraph evaluation flow, which fans out to five evaluators running independently.
5. Each evaluator returns its own score, issues found and recommendations.
6. A score aggregation engine merges the five results into one evaluation.
7. A final report is generated with an overall score and suggestions for improvement.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | Django 6.0 |
| Database | PostgreSQL 17 (via Docker Compose) |
| Orchestration | LangGraph, LangChain |
| LLM | Google Gemini (`google-genai`, `langchain-google-genai`) |
| Web search / evidence retrieval | Tavily |
| HTML parsing | BeautifulSoup4, lxml |
| DB driver | psycopg2-binary |
| Config | python-dotenv |
| Containerization | Docker Compose |
| Language | Python |

## Features

- Evaluate a live webpage against the original prompt or brief it was supposed to satisfy
- Automatic content extraction: plain text, HTML, headings, paragraphs, links, images and metadata from any URL
- Five specialized evaluators running per page, each returning a score, a list of issues and recommendations
- LLM backed checks for the nuanced stuff (prompt alignment, fact verification, search/answer quality, property card context) alongside rule based checks for SEO and technical HTML
- Factual claims get checked against real web evidence through Tavily before Gemini makes a verified/unsupported/uncertain call
- Property card validation for travel style pages, confirming a listed property actually belongs to the page's destination
- Deterministic SEO and technical audits covering titles, meta descriptions, content length, headings, links and images
- One command local Postgres setup through Docker Compose

## Evaluation Modules

Here's what each of the five modules in `docs/` actually checks.

### 1. Prompt Alignment Evaluator

Uses an LLM to judge whether the generated page actually satisfies the original request. This one is purely about content relevance, not technical quality. It checks whether the topics the user asked for are actually covered, whether anything important is missing, whether the page stays on topic or drifts, and whether there's content that's clearly unrelated to the request. It outputs an overall alignment score from 0 to 100. It deliberately ignores HTML structure, SEO, keyword density, links, images and meta tags since those belong to the other modules.

### 2. Knowledge Validation Evaluator

Checks two separate things: whether factual claims on the page are actually true, and whether property cards on the page belong to the right destination.

For claims, a claim extractor pulls factual statements out of the page text, Tavily searches the web for evidence, and Gemini looks at the claim plus that evidence and returns verified, unsupported or uncertain. Unsupported claims become a high severity issue, uncertain ones a medium severity issue.

For property cards, Gemini is given the page's title, headings and context along with each card's location, and returns either valid or context mismatch. So a New York travel guide with a Jersey City apartment listing passes, but the same page listing a Paris hotel gets flagged.

It does not touch keyword density, SEO, readability, search intent or writing style; that's someone else's job.

### 3. SEO Content Quality Evaluator

A rule based evaluator that starts at 100 and deducts points per issue (high severity costs 15, medium costs 8, low costs 3, and the score never drops below 0). It checks:

- Title length (flags missing titles, and anything under 30 or over 60 characters)
- Meta description length (missing, under 120, or over 160 characters)
- Content length (thin content under 300 words up through excessively long content over 4000 words)
- Long paragraphs, anything over 180 words
- Internal link distribution, expecting roughly one internal link per 500 words
- External link distribution, flagging pages with more than 25 external links
- Image to content ratio, expecting roughly one image per 800 words
- Duplicate headings across h1 through h6
- Generic headings like "home", "about" or "services"
- Readability, flagging an average sentence length over 25 words

### 4. Search Quality Evaluator

This one asks an LLM to judge how satisfying the page would be for someone arriving from a search engine. It's not trying to replicate Google's actual ranking algorithm, just judging content quality from the searcher's point of view. It scores search intent match, helpfulness, completeness, natural writing, repetition, how "AI sounding" the content reads, content depth, readability and overall user satisfaction, each on a 0 to 100 scale, and also flags missing sections. It stays out of factual correctness, technical SEO and backlinks; those belong to other modules.

### 5. Technical HTML Evaluator

A rule based structural check on the raw HTML. It looks for a title tag, a meta description, exactly one H1, empty anchor tags, anchors missing an href, images missing alt or src attributes, broken heading hierarchy (like jumping from H1 straight to H4), duplicate id attributes, and basic structural tags (html, head, body). It also checks whether links and image URLs actually resolve by validating their HTTP status. Output is a technical score plus a list of issues and recommendations.

## Optimization and  Pending Work

- The 5 evaluation modules will be parallel instead of sequential edges in langGraph (currently working on feature/frontend-report branch which is not merged with main yet )
- Local llm (Qwen3-1.7b) has been used instead of gemini model for rate limit issue (currently working on feature/frontend-report branch which is not merged with main yet )
- Integration and build the UI scoreboard so results, issues and recommendations are actually visible to a user (currently working on feature/frontend-report branch which is not merged with main yet )

## Setup

If you want to run this locally, here's what you'll need first:

- Python 3.11 or newer
- Docker and Docker Compose (for Postgres)
- A Gemini API key
- A Tavily API key

### 1. Clone the repo

```bash
git clone https://github.com/Parisa-Reza/Qualisto.git
cd Qualisto
```

### 2. Set up a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate      # on Windows use venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure your environment variables

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

```
SECRET_KEY=your-django-secret-key
DEBUG=True

POSTGRES_DB=your_db_name
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_db_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

### 4. Start Postgres

```bash
docker-compose up -d
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the server

```bash
python manage.py runserver
```

The app runs at `http://127.0.0.1:8000/`.

### 7. Run the tests (optional)

Each module has its own test file (things like `test_seo_content_quality.py`, `test_technical_html.py`, `test_knowledge_validation.py`). Run all of them with:

```bash
python manage.py test
```