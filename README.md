# Job Finder

A powerful, containerized web application built with Python, Flask, and Playwright to fetch, filter, and organize job offers from various portals (Stellenwerk and Stepstone). It provides a sleek, dark-themed UI to manage your job hunt locally using an SQLite database.

## Features
- **Headless Browser Scraping**: Uses Playwright to bypass basic anti-bot protections and deep-scrape job descriptions.
- **Dynamic Configuration & Pagination**: Automatically generates target URLs for multiple pages based on a clean `config.yml` setup.
- **Interactive Web UI**: A beautiful, dark-themed Flask frontend built with custom CSS and JavaScript.
- **Live Scraper Updates**: Watch new jobs stream into your UI live via Server-Sent Events (SSE) while the scraper runs in the background.
- **Advanced Filtering & Sorting**: Use multi-select dropdowns to instantly filter jobs by positive and negative keywords.
- **Database Tracking**: Jobs are stored in a local SQLite database (`jobs.db`). Mark jobs as "Done" or delete them permanently so you never review the same job twice.

## Requirements
- Docker and Docker Compose

## Quickstart

1. **Configure Your Scraper**
   Edit `config.yml` to define your target base URLs, the number of pages to scrape, and your positive/negative keywords:
   ```yaml
   stellenwerk_link: "https://www.stellenwerk.de/hamburg"
## Quick Start

1. **Clone the repository.**
2. **Setup your Configuration:**
   Copy the example config file and fill in your keywords and API keys:
   ```bash
   cp config.example.yml config.yml
   ```
   Open `config.yml` in your editor and enter your `gemini_api_key`, along with any target keywords.
3. **Start the application with Docker:**
   ```bash
   docker compose up --build
   ```

3. **Open the Web UI**
   Visit [http://localhost:5000](http://localhost:5000) in your browser.

4. **Start Scraping**
   Click the **"🚀 Run Scraper"** button in the UI to launch the Playwright script in the background. The terminal log will show real-time progress, and new jobs will dynamically appear in your list!

## Development & Manual Setup

If you prefer to run the app outside of Docker:

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install Playwright browser binaries:
   ```bash
   playwright install chromium
   ```
3. Run the Flask server:
   ```bash
   python app.py
   ```
