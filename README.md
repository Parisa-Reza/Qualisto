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
| Containerization | Docker |
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

- Uses an LLM to judge whether the generated page actually satisfies the original request.
- Verifies if the page matches the requested location or subject
- Checks if specific sections or information requested by the user are present
- Identifies parts of the prompt left unaddressed
- Flags sections unrelated to the target destination or topic
- Detects internal conflicts with the original request
- Requires every issue to pinpoint exact locations and every recommendation to specify actionable changes
- Receives the original user request and the generated webpage content
- The LLM judges content relevance while ignoring SEO, code, and writing quality
- Outputs an alignment score from 0 to 100
- Automatically assigns uniform issue severity based on the score tier
- Formats final results into scores, missing requirements, off-topic sections, structured issues, and actionable recommendations

### 2. Knowledge Validation Evaluator

- Verifies factual correctness, destination correctness, and property card relevance while ignoring SEO and HTML quality
- Performs overall general knowledge validation followed by individual property card validation
- Builds search queries from page titles and headings to fetch external evidence via Tavily Search
- Passes webpage content and search evidence to Gemini LLM to classify claims as verified, unsupported, or uncertain
- Validates every extracted property card independently to check for destination context mismatches
- Uses ThreadPoolExecutor to run property card validations concurrently and drastically reduce execution time
- Generates specific issues and recommendations whenever a property card context mismatch occurs
- Calculates the final score by subtracting penalties from the base Gemini score for each card mismatch
- Returns a final KnowledgeValidationResult containing scores, claims, issues, and recommendations

### 3. Technical HTML Evaluator

- Performs rule-based validation of structural and technical webpage health across six categories: Structure, Metadata, Links, Images, Accessibility, and HTML Validation
- Checks foundational HTML elements, unique IDs, heading hierarchies, title and meta description tags, and element completeness
- Validates links and images by inspecting attributes, text content, and live URL reachability
- Provides precise, developer-readable issue locations using CSS-style breadcrumbs, line numbers, and truncated outer HTML snippets
- Calculates scores starting at 100 with fixed per-category penalties rather than per-issue deductions, floored at a minimum score of 0
- Uses concurrent ThreadPoolExecutor workers (up to 10 max workers) with a 5-second timeout and HEAD-first, GET-fallback logic to accelerate live URL validations
- Returns a final technical HTML score along with a structured list of issues and matching improvement recommendations



### 4. Search Quality Evaluator

- Evaluates search content quality and visitor experience across signals like helpfulness, completeness, natural writing, repetition, AI-feel, depth, readability, and user satisfaction
- Generates an overall score from 0 to 100 via LLM without penalizing pages simply for being AI-generated
- Automatically assigns uniform issue severity based on score tiers (High for below 40, Medium for 40 to 69, Low for 70 and above)
- Ignores technical SEO, keyword density, backlinks, Core Web Vitals, schema markup, image ALT text, and factual accuracy
- Returns overall score, search intent summary, individual signal scores, missing sections, and structured issues and recommendations

### 5. SEO Content Quality Evaluator

- Starts every page at a score of 100, deducting 15 for High, 8 for Medium, and 3 for Low severity issues down to a minimum of 0
- Checks title length for missing, too short (<30 chars), or too long (>60 chars) conditions
- Checks meta description length for missing, too short (<120 chars), or too long (>160 chars) conditions
- Evaluates total word count for thin (<300), low (300-599), very long (2501-4000), or excessive (>4000) content ranges
- Flags long paragraphs if any single paragraph exceeds 180 words
- Evaluates internal link coverage (expected ~1 per 500 words, must start with a slash) and external link limits (flags if >25)
- Checks image coverage, expecting roughly 1 image for every 800 words of content
- Identifies duplicate headings across h1 through h6 and flags generic headings against a predefined blocklist
- Assesses readability by flagging average sentence lengths exceeding 25 words
- Extracts target topics from the user prompt via language model to check for missing topics, weak placements, and keyword density bounds (0.5% to 2%)



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

