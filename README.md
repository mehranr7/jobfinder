# JobFinder

An intelligent, self-hosted job aggregation platform that automatically discovers, scrapes, and evaluates job listings from multiple German job portals — then ranks them against your CV using Google's Gemini API.

Built with Python, Flask, Playwright, and Docker. Designed to run locally with zero cloud dependencies beyond the LLM API.

## Features

- **Multi-Platform Scraping** — Aggregates listings from Stellenwerk, Stepstone, Xing, Talent.com, Kimeta, and Glassdoor with source-aware pagination and cross-platform deduplication.
- **AI-Powered Evaluation** — A background daemon continuously scores new jobs against your CV(s) using Google Gemini, producing a 0–100 match score, a reasoning summary, a recommended CV variant, and a draft cover letter.
- **Live Streaming UI** — Server-Sent Events push scraper and evaluator logs to the browser in real time. New job cards appear dynamically without page reloads.
- **Advanced Filtering & Sorting** — Multi-select keyword and negative-keyword filters, platform filters, status filters, and sort-by-date/score controls — all client-side for instant response.
- **Application Tracking** — Track each job through configurable pipeline stages (e.g., Unseen → Applied → Interview → Offer). Attach notes and assign CV types per listing.
- **CSV Export** — Export any filtered subset of jobs to a UTF-8 CSV report for offline review.
- **Containerized Deployment** — Single `docker compose up` with persistent volumes for the database, configuration, CVs, and frontend assets.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (UI)                         │
│   Dark-themed SPA  ·  SSE streams  ·  Client-side filters   │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────┐
│                     Flask Application                       │
│   REST API  ·  SSE endpoints  ·  Jinja2 templates           │
├──────────┬──────────────────────────────┬───────────────────┤
│ Scraper  │          Database            │    Evaluator      │
│ Module   │         (SQLite)             │    Daemon         │
│          │                              │                   │
│ Playwright  ────►  jobs.db  ◄────  Gemini API               │
│ + requests         (persistent)         (scoring + letters) │
└──────────┴──────────────────────────────┴───────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask |
| Scraping | Playwright (Chromium), Requests, BeautifulSoup4 |
| AI Evaluation | Google Gemini API (`google-generativeai`) |
| Database | SQLite3 |
| Frontend | Jinja2, Vanilla JS, Custom CSS (dark theme) |
| Deployment | Docker, Docker Compose |
| Real-time | Server-Sent Events (SSE) |

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/mehranr7/jobfinder.git
cd jobfinder
cp config.example.yml config.yml
```

Edit `config.yml` with your settings:
- Set your `gemini_api_key`
- Configure target job portal URLs and page counts
- Define your positive/negative keyword lists

### 2. Set Up CV Evaluation (Optional)

```bash
mkdir cvs
# Place your PDF CVs in the cvs/ directory
```

Create `llm_instruction.txt` with your custom evaluation prompt for the Gemini model.

### 3. Run with Docker

```bash
docker compose up --build
```

Open [http://localhost:4567](http://localhost:4567) in your browser.

### 4. Run Without Docker

```bash
pip install -r requirements.txt
playwright install chromium
python app.py
```

## Configuration Reference

| Key | Description | Default |
|-----|-------------|---------|
| `port` | Server port | `4567` |
| `gemini_api_key` | Google Gemini API key | — |
| `evaluator_models` | Ordered Gemini text-model priority list; falls back to the next model on an API error or rate limit | Highest-capability-first list in `config.example.yml` |
| `evaluator_model_cooldown_s` | Seconds to skip a model after an unavailable-model or rate-limit error | `300` |
| `evaluator_delay_s` | Seconds between evaluations (rate limiting) | `15` |
| `cv_paths` | List of PDF CV file paths | `[]` |
| `stellenwerk_link` | Stellenwerk search URL or list of URLs | — |
| `stepstone_link` | Stepstone search URL or list of URLs | — |
| `xing_link` | Xing search URL or list of URLs | — |
| `talent_link` | Talent.com search URL(s), replacing Neuvoo | — |
| `kimeta_link` | Kimeta search URL(s), first result batch only | — |
| `glassdoor_link` | Glassdoor search URL or list of URLs | — |
| `*_pages` | Page count for the matching source | `1` |
| `block_heavy_resources` | Skip images, fonts, and media during browser extraction | `true` |
| `keywords` | Positive keywords for matching | `[]` |
| `negative_keywords` | Negative keywords for filtering | `[]` |
| `app_states` | Custom application pipeline stages | `[Unseen, Applied, ...]` |
| `cv_types` | CV variant labels | `[Software, Data, ...]` |

## Project Structure

```
jobfinder/
├── app.py                 # Flask application and API routes
├── scraper.py             # Multi-platform scraping engine
├── source_registry.py     # Adapter registry and shared lightweight helpers
├── public_sources.py      # Talent, Kimeta, and Glassdoor adapters
├── evaluator.py           # Gemini-powered job evaluation daemon
├── database.py            # SQLite data access layer
├── utils.py               # Text cleaning, date parsing, helpers
├── config.example.yml     # Configuration template
├── requirements.txt       # Pinned Python dependencies
├── Dockerfile             # Multi-stage container build
├── docker-compose.yml     # Production compose configuration
├── static/
│   ├── css/style.css      # Dark-themed UI stylesheet
│   └── js/script.js       # Client-side filtering, SSE, and interactions
└── templates/
    ├── index.html          # Main application page
    ├── job_card.html       # Individual job card component
    └── job_cards.html      # Job card list renderer
```

Optional local-only adapters can be placed in `private_sources/`. That directory
is git-ignored and discovered at runtime, so public builds remain fully functional
when it is absent. Their configuration remains local and is intentionally omitted
from `config.example.yml`.
Every `*_link` setting accepts either one URL or a YAML list of URLs, allowing a
source to cover multiple markets such as Hamburg and Germany-wide remote roles.

Before enabling a portal, review its current terms and robots policy and obtain
permission where required. An empty link disables a source without affecting the
rest of the scraper.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
