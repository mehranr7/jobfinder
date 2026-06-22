from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://jobs.adesso-group.com/?currentPage=1&pageSize=100&brand=adesso+SE&orderBy=datePosted&isDesc=true", timeout=60000)
    page.wait_for_timeout(5000)
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True).lower()
    print("PAGE TEXT DUMP:")
    print(text[:1000])
    
    keywords = ["fulltime", "part-time", "teilzeit", "vollzeit", "karrierelevel", "berufsfeld", "abteilung", "department", "standort", "location", "suche", "filter"]
    for kw in keywords:
        if kw in text:
            print(f"FOUND: {kw}")
    browser.close()
