"""Public source adapters that are independent from database persistence."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from source_registry import (
    SourceAdapter,
    canonicalize_url,
    fetch_soup,
    make_job,
    normalize_space,
    parse_listing_date,
    set_query_parameter,
)


def _as_soup(html):
    return html if isinstance(html, BeautifulSoup) else BeautifulSoup(html, "html.parser")


def _locator_text(page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count() > 0:
            text = normalize_space(locator.inner_text(timeout=5000))
            if text:
                return text
    return None


def _http_description(job, source_name: str, selectors: tuple[str, ...]) -> str | None:
    soup = fetch_soup(job["link"], source_name)
    if soup is None:
        return None
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = normalize_space(element.get_text(" ", strip=True))
            if text:
                return text
    return None


def parse_talent_html(
    html: str, base_url: str, keywords: list[str], negative_keywords: list[str]
) -> list[dict]:
    soup = _as_soup(html)
    jobs = []
    for card in soup.select('article[data-testid="job-card-unified"]'):
        title_tag = card.select_one('h2[class*="JobCard_title"]')
        company_tag = card.select_one('span[class*="JobCard_company"]')
        link_tag = card.select_one('a[href*="/view?id="]')
        if not title_tag or not link_tag:
            continue

        time_tag = card.find("time")
        raw_date = time_tag.get("datetime", "") if time_tag else ""
        preview_tag = card.select_one('p[class*="JobCard_snippet"]')
        link = canonicalize_url(urljoin(base_url, link_tag["href"]), ("id",))
        job = make_job(
            title=title_tag.get_text(" ", strip=True),
            link=link,
            company=company_tag.get_text(" ", strip=True) if company_tag else "Unknown Company",
            platform="Talent.com",
            card_text=card.get_text(" ", strip=True),
            keywords=keywords,
            negative_keywords=negative_keywords,
            date=parse_listing_date(raw_date),
            preview_text=preview_tag.get_text(" ", strip=True) if preview_tag else "",
        )
        if job:
            jobs.append(job)
    return jobs


def scrape_talent(page, url, keywords, negative_keywords):
    soup = fetch_soup(url, "Talent.com")
    return parse_talent_html(soup, url, keywords, negative_keywords) if soup else []


def extract_talent_description(page, job):
    return _locator_text(
        page,
        (
            '[data-testid="job-description"]',
            '[class*="JobDescription"]',
            'main article',
        ),
    )


def fetch_talent_description(job):
    return _http_description(
        job,
        "Talent.com detail",
        ('div[class*="styles_jobDescriptionColumn"]', '[class*="jobDescription"]', "main"),
    )


def parse_kimeta_html(
    html: str, base_url: str, keywords: list[str], negative_keywords: list[str]
) -> list[dict]:
    soup = _as_soup(html)
    jobs = []
    for card in soup.select("div.offer"):
        link_tag = card.select_one("div.offer-head > a[href]")
        title_tag = card.select_one("h3.jt")
        company_tag = card.select_one("div.cn")
        if not link_tag or not title_tag:
            continue

        card_text = card.get_text(" ", strip=True)
        date_match = re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", card_text)
        raw_date = date_match.group(0) if date_match else (
            "Heute" if " Neu " in f" {card_text} " else ""
        )
        preview_tag = card.select_one("div.summary")
        link = canonicalize_url(urljoin(base_url, link_tag["href"]))
        job = make_job(
            title=title_tag.get_text(" ", strip=True),
            link=link,
            company=company_tag.get_text(" ", strip=True) if company_tag else "Unknown Company",
            platform="Kimeta",
            card_text=card_text,
            keywords=keywords,
            negative_keywords=negative_keywords,
            date=parse_listing_date(raw_date),
            preview_text=preview_tag.get_text(" ", strip=True) if preview_tag else "",
        )
        if job:
            jobs.append(job)
    return jobs


def scrape_kimeta(page, url, keywords, negative_keywords):
    soup = fetch_soup(url, "Kimeta")
    return parse_kimeta_html(soup, url, keywords, negative_keywords) if soup else []


def extract_kimeta_description(page, job):
    return _locator_text(
        page,
        (
            '[class*="job-description"]',
            '[class*="description"]',
            "main",
        ),
    )


def fetch_kimeta_description(job):
    return _http_description(
        job,
        "Kimeta detail",
        ("main article", "div.content-innerhtml", "main"),
    )


def parse_glassdoor_html(
    html: str, base_url: str, keywords: list[str], negative_keywords: list[str]
) -> list[dict]:
    soup = _as_soup(html)
    jobs = []
    for card in soup.select('li[data-test="jobListing"]'):
        title_tag = card.select_one('a[data-test="job-title"]')
        company_tag = card.select_one('span[class*="EmployerProfile_compactEmployerName"]')
        age_tag = card.select_one('[data-test="job-age"]')
        preview_tag = card.select_one('[data-test="descSnippet"]')
        if not title_tag or not title_tag.get("href"):
            continue

        link = canonicalize_url(urljoin(base_url, title_tag["href"]), ("jl",))
        job = make_job(
            title=title_tag.get_text(" ", strip=True),
            link=link,
            company=company_tag.get_text(" ", strip=True) if company_tag else "Unknown Company",
            platform="Glassdoor",
            card_text=card.get_text(" ", strip=True),
            keywords=keywords,
            negative_keywords=negative_keywords,
            date=parse_listing_date(age_tag.get_text(" ", strip=True) if age_tag else ""),
            preview_text=preview_tag.get_text(" ", strip=True) if preview_tag else "",
        )
        if job:
            job_ids = parse_qs(urlparse(link).query).get("jl", [])
            if job_ids:
                # Direct job pages commonly return a 403 challenge. Selecting the
                # same job inside its accessible search page exposes the complete
                # server-rendered description pane.
                job["_detail_url"] = set_query_parameter(base_url, "jl", job_ids[0])
            jobs.append(job)
    return jobs


def scrape_glassdoor(page, url, keywords, negative_keywords):
    soup = fetch_soup(url, "Glassdoor")
    return parse_glassdoor_html(soup, url, keywords, negative_keywords) if soup else []


def fetch_glassdoor_description(job):
    detail_url = job.get("_detail_url")
    if not detail_url:
        return None

    soup = fetch_soup(detail_url, "Glassdoor detail pane")
    if soup is None:
        return None

    for selector in (
        '[class*="JobDetails_jobDescription"]',
        '[data-test="jobDescriptionContent"]',
        '[class*="jobDescriptionContent"]',
    ):
        element = soup.select_one(selector)
        if not element:
            continue

        description_text = normalize_space(element.get_text(" ", strip=True))
        title = normalize_space(job.get("title", ""))
        if title and title.casefold() not in description_text.casefold():
            continue
        if len(description_text) >= 150:
            return str(element)
    return None


def extract_glassdoor_description(page, job):
    for selector in (
        '[class*="JobDetails_jobDescription"]',
        '[data-test="jobDescriptionContent"]',
        '[class*="jobDescriptionContent"]',
    ):
        locator = page.locator(selector).first
        if locator.count() == 0:
            continue
        text = normalize_space(locator.inner_text(timeout=5000))
        title = normalize_space(job.get("title", ""))
        if len(text) >= 150 and (not title or title.casefold() in text.casefold()):
            return locator.inner_html(timeout=5000)
    return None


def _custom_company_name(url: str) -> str:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    label = host.split(".", 1)[0] if host else "Custom Company"
    label = re.sub(r"[-_]+", " ", label).strip()
    return label.title() or "Custom Company"


def _custom_job_container(link_tag):
    """Find a likely job card without requiring a company-specific selector."""
    card = link_tag.find_parent(["article", "li"])
    if card:
        return card

    for parent in link_tag.parents:
        classes = " ".join(parent.get("class", []))
        identifier = f"{classes} {parent.get('id', '')}".lower()
        if any(marker in identifier for marker in ("job", "position", "vacanc", "opening", "career", "stelle", "angebot")):
            return parent
    return link_tag


def parse_custom_career_html(
    html: str, base_url: str, keywords: list[str], negative_keywords: list[str]
) -> list[dict]:
    """Extract keyword-matching job links from a generic company career page.

    Company career pages have no common markup, so this intentionally uses a
    conservative heuristic: only HTTP(S) links whose visible title matches a
    configured keyword are emitted. Site-specific adapters can be added later
    when a company needs more precise selectors.
    """
    soup = _as_soup(html)
    jobs = []
    seen_links = set()
    company = _custom_company_name(base_url)

    for link_tag in soup.select("a[href]"):
        href = str(link_tag.get("href", "")).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        parsed_link = urlparse(urljoin(base_url, href))
        if parsed_link.scheme not in {"http", "https"}:
            continue
        link = urlunparse(parsed_link._replace(fragment=""))
        if not link or link.rstrip("/") == base_url.rstrip("/") or link in seen_links:
            continue

        card = _custom_job_container(link_tag)
        heading = link_tag.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        if heading is None and card is not link_tag:
            heading = card.find(["h1", "h2", "h3", "h4", "h5", "h6"])
        title = normalize_space(heading.get_text(" ", strip=True) if heading else link_tag.get_text(" ", strip=True))
        if not title or len(title) > 180:
            continue

        card_text = normalize_space(card.get_text(" ", strip=True))
        time_tag = card.find("time") if card is not None else None
        raw_date = ""
        if time_tag:
            raw_date = time_tag.get("datetime", "") or time_tag.get_text(" ", strip=True)
        if not raw_date:
            date_match = re.search(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b", card_text)
            raw_date = date_match.group(0) if date_match else ""

        job = make_job(
            title=title,
            link=link,
            company=company,
            platform="Custom Careers",
            card_text=card_text,
            keywords=keywords,
            negative_keywords=negative_keywords,
            date=parse_listing_date(raw_date),
            preview_text=card_text,
        )
        if job:
            seen_links.add(link)
            jobs.append(job)
    return jobs


def scrape_custom_careers(page, url, keywords, negative_keywords):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(750)
        return parse_custom_career_html(page.content(), url, keywords, negative_keywords)
    except Exception as exc:
        print(f"  [!] Failed to load custom career URL: {exc}")
        return []


def _unchanged_first_page(url: str, page_number: int) -> str:
    return url


def _query_page(parameter: str):
    def builder(url: str, page_number: int) -> str:
        return url if page_number == 1 else set_query_parameter(url, parameter, page_number)

    return builder


PUBLIC_SOURCES = (
    SourceAdapter(
        name="Talent.com",
        link_key="talent_link",
        pages_key="talent_pages",
        page_url=_query_page("p"),
        scrape=scrape_talent,
        fetch_description=fetch_talent_description,
        extract_description=extract_talent_description,
    ),
    SourceAdapter(
        name="Kimeta",
        link_key="kimeta_link",
        pages_key="kimeta_pages",
        page_url=_unchanged_first_page,
        scrape=scrape_kimeta,
        fetch_description=fetch_kimeta_description,
        extract_description=extract_kimeta_description,
        max_pages=1,
    ),
    SourceAdapter(
        name="Glassdoor",
        link_key="glassdoor_link",
        pages_key="glassdoor_pages",
        page_url=_query_page("page"),
        scrape=scrape_glassdoor,
        fetch_description=fetch_glassdoor_description,
        extract_description=extract_glassdoor_description,
    ),
    SourceAdapter(
        name="Custom Careers",
        link_key="custom_links",
        pages_key="custom_pages",
        page_url=_unchanged_first_page,
        scrape=scrape_custom_careers,
        max_pages=1,
    ),
)
