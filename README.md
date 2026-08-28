# Qualisto

## Description

Qualisto is an AI powered engine that evaluates AI-generated webpage content based on prompt alignment, SEO content quality, technical health, search quality, and factual correctness.

You give it a prompt (whatever the page was supposed to accomplish) and a URL. Qualisto fetches that page, pulls out its text, HTML and metadata, then runs it through five separate evaluation modules. Each module scores the page on a different dimension: does it match the original prompt, are the facts on it actually true, is the SEO solid, would a search engine visitor be satisfied, and is the HTML technically sound. Those scores eventually get combined into one report with an overall grade and a list of things to fix.

## Workflow
<img width="1779" height="2380" alt="image" src="https://github.com/user-attachments/assets/38bc444c-7ca0-44bb-b3bf-8f12d5e4a606" />


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
| Target webpage render | Playwright|
| HTML parsing | BeautifulSoup4, lxml |
| Config | python-dotenv |
| Containerization | Docker |
| Language | Python |

## Features

- Evaluate a live webpage against the original prompt or brief it was supposed to satisfy
- Automatic content extraction: plain text, HTML, headings, paragraphs, links, images and metadata from any URL
- Five specialized evaluators running per page, each returning a score, a list of issues and recommendations
- LLM backed checks for the nuanced stuff (prompt alignment, fact verification, search/answer quality, property card context) alongside rule based checks for SEO and technical HTML
- Factual claims get checked against real web evidence through Tavily before Gemini makes a verified/unsupported/uncertain call
- Property card validation for travel style pages, confirming a listed property actually belongs to the page's destination , hero image validation
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
- Receives the original user request and the generated webpage content
- The LLM judges content relevance while ignoring SEO, code, and writing quality
- Outputs an alignment score from 0 to 100
- Automatically assigns uniform issue severity based on the score tier
- Formats final results into scores, missing requirements, off-topic sections, structured issues, and actionable recommendations

### 2. Knowledge Validation Evaluator

This module ensures the webpage’s factual and geographic content matches the user’s request. It runs four sub‑validations:

- **General Knowledge Validation**  
  - Checks the whole page for factual errors, unsupported claims, contradictions, and content that belongs to another destination.  
  - Uses the user prompt as the sole authority for the intended destination (webpage title and headings are **not** trusted).  
  - Collects external evidence via Tavily and passes it to an LLM that returns a score (0–100), verified/unsupported/uncertain claims, and paired issue‑recommendation findings.

- **Property Card Validation** (for travel pages)  
  - Validates that each property card (hotel, villa, cottage, etc.) geographically belongs to the requested destination.  
  - **Deterministic pre‑check** – compares country codes (ISO), city names (exact, substring, prefix), and location strings; returns `valid`, `context_mismatch`, or `ambiguous`.  
  - **Destination extraction** now uses deterministic list parsing first – if the prompt is a quoted list, line‑separated list, or a comma‑separated list of “Place, Country” pairs, it parses those directly to avoid LLM collapsing multiple destinations into one. Only country resolution uses the LLM.  
  - Only `ambiguous` cards go to the expensive path: country identity resolution (Tavily + LLM), then a strict geographic LLM that decides if the city is **administratively inside** any of the intended destinations (metro proximity or shared airport are explicitly rejected).  
  - Ambiguous cards are processed in parallel via `ThreadPoolExecutor` (default 4 workers) to speed up external calls.  
  - Score = (`valid_cards` / `total_cards`) × 100.

- **Hero Image Validation**  
  - Validates that hero‑section images visually depict the requested destination.  
  - Uses a **multimodal Gemini** model that actually “looks” at the images – the only path requiring vision.  
  - Images are converted to Gemini‑compatible parts (data URIs or downloaded HTTP URLs).  
  - Each image is classified as `valid`, `context_mismatch`, or `uncertain`. `uncertain` images are logged but **do not** affect the score; only confirmed mismatches lower the score.  
  - The entire batch of images is sent in one Gemini call (not one per image).  
  - If Gemini is unavailable, the destination cannot be resolved, or no images survive conversion, the path is skipped with a neutral score of 100 (fails safe).

- **Property Type Tabs Validation** (new)  
  - Checks that the actual property types listed under a specific tab (e.g., “Villas”) match the tab’s label.  
  - Purely deterministic – uses string normalisation and equality, **no LLM** calls.  
  - If a tab labelled “Villas” contains a property of type “Apartment”, a high‑severity issue is raised.  
  - Score = (number of correct type–tab pairings / total pairings) × 100.

The final Knowledge Validation score is the **minimum** of all scores from sub‑validations that actually ran (general is always included; property card, hero image, and property type scores are included only when that content exists). This conservative approach ensures that no single weak area is hidden by stronger ones.

### 3. Technical HTML Evaluator

- Performs rule-based validation of structural and technical webpage health across six categories: Structure, Metadata, Links, Images, Accessibility, and HTML Validation
- Checks foundational HTML elements, unique IDs, heading hierarchies, title and meta description tags, and element completeness
- Validates links and images by inspecting attributes, text content, and live URL reachability
- Provides precise, developer-readable issue locations using CSS-style breadcrumbs
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

## Evaluation table
<img width="1140" height="275" alt="Screenshot from 2026-08-07 12-11-32" src="https://github.com/user-attachments/assets/bacaa08f-2735-4c1f-93ba-0a668da63dc5" />

## Trade-offs and Design Constraints

The project was developed under significant hardware and resource constraints. These limitations influenced the choice of LLMs, the evaluation architecture, and the balance between reasoning quality and execution time.

### 1. Hardware Limitations

The primary development environment was:

- **RAM:** 8 GB
- **CPU:** Intel Core i3-4130, 4 threads
- **GPU:** No dedicated GPU
- **LLM inference:** CPU-based through Ollama

Because inference was CPU-based, larger models caused higher memory usage and significantly longer execution times.

###  2. Local LLM Trade-offs

####  Qwen3:1.7B

Qwen3:1.7B was initially selected because it was practical to run locally on the available hardware.

**Advantages:**
- Low memory requirements
- Free local inference
- Suitable for rapid development and testing

**Limitations:**
- Weaker reasoning
- More prone to hallucination
- Less reliable for complex geographic reasoning
- Complete evaluation could take approximately **2.5 hours**

It was therefore useful for prototyping, but not always reliable for difficult location and jurisdiction decisions.

####  Qwen2.5:3B

Qwen2.5:3B was considered/tested to improve reasoning quality.

The trade-off was:

> **More parameters → potentially better reasoning → higher memory usage and slower CPU inference.**

It improved model capacity but did not remove the fundamental CPU-performance limitation.

####  Why Qwen3:4B Was Not Used

Qwen3:4B was considered for its stronger reasoning capability but was not selected for the full workflow. Running a larger model alongside Django, LangGraph, PostgreSQL, web-processing components, and Ollama would place excessive pressure on an 8 GB RAM / 4-thread system.

Therefore, the project prioritized **practical local execution over maximum model capacity**.

###  3. Gemini 3.1 Flash-Lite for Image Validation

Text-only local models were not sufficient for **hero-image validation**, which requires actual visual understanding.

The project therefore used **Gemini 3.1 Flash-Lite** for image validation:

- **Qwen:** text reasoning and structured evaluation
- **Gemini:** visual validation of hero images

For example, if a page is about **Cox's Bazar** but its hero image depicts **Bali**, visual analysis is required rather than relying only on filenames, URLs, or ALT text.

This hybrid approach kept most text evaluation local while using a multimodal model where visual reasoning was necessary.

###  4. Deterministic Validation vs LLM Reasoning

The project also minimized unnecessary LLM usage by handling obvious cases deterministically.

For example, if a property card contains:

```text
data-property_country_code="BS"
```

and the intended country is known to be The Bahamas, the result can be determined without an LLM.

The general strategy was:

```text
Deterministic validation
        ↓
Clearly resolvable?
   ┌────┴────┐
  YES        NO
   ↓          ↓
Decision   Search + LLM
```

This reduces LLM calls, improves latency, and limits hallucination.

###  5. Overall Engineering Trade-off

The final architecture balances **accuracy, reasoning capability, latency, hardware limitations, and development cost**.

- **Qwen3:1.7B:** practical and lightweight, but weaker reasoning
- **Qwen2.5:3B:** stronger model capacity with higher computational cost
- **Qwen3:4B:** potentially stronger, but impractical for the available hardware
- **Gemini 3.1 Flash-Lite:** dedicated multimodal validation for hero images
- **Deterministic rules:** used for straightforward validation
- **Tavily/search:** provides external evidence for factual and geographic verification
- **Hybrid architecture:** provides the most practical balance between quality and execution constraints

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
