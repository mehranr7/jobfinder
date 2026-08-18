"""Public source adapters that are independent from database persistence."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

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
)
