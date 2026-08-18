"""Shared source-adapter primitives for the scraper.

This module deliberately has no database imports. Listing parsers can therefore
be tested without initializing, migrating, or writing the production database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import importlib.util
import os
import re
from typing import Callable, Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

import utils


ScrapeFunction = Callable[[object, str, list[str], list[str]], list[dict]]
PageUrlBuilder = Callable[[str, int], str]
DescriptionExtractor = Callable[[object, dict], Optional[str]]
DescriptionFetcher = Callable[[dict], Optional[str]]


@dataclass(frozen=True)
class SourceAdapter:
    """One job portal's configuration, pagination, and extraction behavior."""

    name: str
    link_key: str
    pages_key: str
    page_url: PageUrlBuilder
    scrape: ScrapeFunction
    fetch_description: Optional[DescriptionFetcher] = None
    extract_description: Optional[DescriptionExtractor] = None
    navigate_to_detail: bool = True
    max_pages: Optional[int] = None


_HTTP = requests.Session()
_HTTP.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }
)


def fetch_soup(url: str, source_name: str, timeout: int = 20) -> Optional[BeautifulSoup]:
    """Fetch server-rendered HTML using one shared, lightweight HTTP session."""

    try:
        response = _HTTP.get(url, timeout=timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as exc:
        print(f"  [!] Failed to load {source_name} URL: {exc}")
        return None


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def matched_terms(text: str, terms: Iterable[str]) -> list[str]:
    return [term for term in terms if re.search(re.escape(term), text or "", re.IGNORECASE)]


def make_job(
    *,
    title: str,
    link: str,
    company: str,
    platform: str,
    card_text: str,
    keywords: list[str],
    negative_keywords: list[str],
    date: str = "Unknown",
    preview_text: str = "",
) -> Optional[dict]:
    """Build the unchanged database-facing job contract after title filtering."""

    title = normalize_space(title)
    if not title or not link:
        return None

    positive_matches = matched_terms(title, keywords)
    if not positive_matches:
        return None

    card_text = normalize_space(card_text)
    return {
        "title": title,
        "date": date or "Unknown",
        "link": link,
        "company": normalize_space(company) or "Unknown Company",
        "platform": platform,
        "keyword": ", ".join(positive_matches),
        "negative_keyword": ", ".join(matched_terms(card_text, negative_keywords)),
        "preview_text": normalize_space(preview_text or card_text),
    }


def set_query_parameter(url: str, key: str, value: object) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def canonicalize_url(url: str, keep_parameters: Iterable[str] = ()) -> str:
    parsed = urlparse(url)
    allowed = set(keep_parameters)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key in allowed]
    return urlunparse(parsed._replace(query=urlencode(query), fragment=""))


def parse_listing_date(raw_date: str) -> str:
    raw_date = normalize_space(raw_date)
    if not raw_date:
        return "Unknown"
    if re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", raw_date):
        return raw_date.split("T", 1)[0]
    for date_format in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw_date, date_format).date().isoformat()
        except ValueError:
            pass

    german_age = re.fullmatch(r"(\d+)\s*T\+?", raw_date, re.IGNORECASE)
    if german_age:
        raw_date = f"vor {german_age.group(1)} Tagen"
    raw_date = re.sub(r"(\d+)\+\s*(?=[A-Za-zÄÖÜäöü])", r"\1 ", raw_date)
    raw_date = re.sub(r"(?<=\d)\s*Std\.?\b", " Stunden", raw_date, flags=re.IGNORECASE)
    return utils.parse_relative_date(raw_date)


def build_targets(config: dict, adapters: Iterable[SourceAdapter]) -> list[dict]:
    targets = []
    for adapter in adapters:
        configured_links = config.get(adapter.link_key, "")
        if isinstance(configured_links, (list, tuple)):
            links = [str(link or "").strip() for link in configured_links]
        else:
            links = [str(configured_links or "").strip()]
        links = list(
            dict.fromkeys(
                link for link in links if link.lower().startswith(("http://", "https://"))
            )
        )
        if not links:
            continue

        try:
            page_count = max(1, int(config.get(adapter.pages_key, 1)))
        except (TypeError, ValueError):
            page_count = 1

        if adapter.max_pages is not None and page_count > adapter.max_pages:
            print(
                f"  [!] {adapter.name} currently supports {adapter.max_pages} page(s); "
                f"clamping configured value {page_count}."
            )
            page_count = adapter.max_pages

        for link in links:
            for page_number in range(1, page_count + 1):
                targets.append(
                    {
                        "url": adapter.page_url(link, page_number),
                        "domain": adapter.name,
                        "page": page_number,
                    }
                )
    return targets


def load_private_sources(base_dir: str) -> list[SourceAdapter]:
    """Load optional, git-ignored local adapters without making them required."""

    private_dir = os.path.join(base_dir, "private_sources")
    if not os.path.isdir(private_dir):
        return []

    sources: list[SourceAdapter] = []
    for filename in sorted(os.listdir(private_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        path = os.path.join(private_dir, filename)
        module_name = f"_jobfinder_private_{os.path.splitext(filename)[0]}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                raise ImportError("unable to create module spec")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module_sources = getattr(module, "SOURCES", ())
            for source in module_sources:
                if not isinstance(source, SourceAdapter):
                    raise TypeError(f"{filename} exported a non-SourceAdapter value")
                sources.append(source)
        except Exception as exc:
            print(f"  [!] Optional private source {filename} was skipped: {exc}")

    return sources
