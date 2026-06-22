import re
import random
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    def __init__(self, keywords, delay_min_ms, delay_max_ms):
        self.keywords = keywords
        self.delay_min_ms = delay_min_ms
        self.delay_max_ms = delay_max_ms
        
    @staticmethod
    def truncate(s, length=60):
        return s if len(s) <= length else s[:length-3] + "..."

    @staticmethod
    def clean_text(html_content):
        """
        Cleans raw HTML content by removing scripts, styles, and other non-visible elements.
        Returns the visible text cleanly formatted with line breaks.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup(["script", "style", "header", "footer", "nav", "noscript", "svg", "img"]):
            tag.extract()
        text = soup.get_text(separator='\n', strip=True)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text

    @abstractmethod
    def scrape(self, page, url):
        """
        Scrape a URL and return a list of dictionaries (or JobOffer objects).
        """
        pass
        
    def perform_deep_scrape(self, page, job):
        """
        Takes a job dictionary, navigates to its link, and updates the description.
        Returns the modified job dictionary.
        """
        try:
            page.goto(job['link'], timeout=15000)
            page.wait_for_load_state("domcontentloaded")
            html = page.content()
            job['description'] = self.clean_text(html)
        except Exception as e:
            job['description'] = "Failed to extract content."
            
        page.wait_for_timeout(random.randint(self.delay_min_ms, self.delay_max_ms))
        return job
