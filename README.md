# Job Finder

A powerful web scraper built with Playwright to fetch, filter, and organize job offers from various portals (Stellenwerk, Indeed, Stepstone). It generates a local, interactive HTML report with advanced sorting, filtering, and local state-tracking capabilities.

## Features
- **Headless Browser Scraping**: Uses Playwright to bypass basic anti-bot protections.
- **Categorized Results**: Groups scraped jobs by domain for readability.
- **Interactive Report**: Generates a `results.html` file with JavaScript-based filtering (by keyword, status) and sorting (by date, title).
- **"Mark as Done" Tracking**: Keeps track of processed jobs using your browser's local storage so you don't evaluate the same job twice.
- **YAML Configuration**: Easily manage URLs and keywords via `config.yml`.

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install Playwright browser binaries:
   ```bash
   playwright install chromium
   ```

## Usage

1. Configure your target URLs and keywords in `config.yml`.
2. Run the scraper:
   ```bash
   python scraper.py
   ```
3. Open the generated `results.html` in your browser to view and track your job offers!
