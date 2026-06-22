import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper

class GenericScraper(BaseScraper):
    def __init__(self, keywords, delay_min_ms, delay_max_ms, job_link_keywords):
        super().__init__(keywords, delay_min_ms, delay_max_ms)
        self.job_link_keywords = job_link_keywords

    def scrape(self, page, url):
        jobs = []
        page.goto(url)
        
        # Wait a bit for dynamic React/Vue apps to load their links
        page.wait_for_timeout(5000)
        
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        a_tags = soup.find_all("a", href=True)
        
        # To avoid duplicates if the same job is linked multiple times
        seen_links = set()
        
        for a_tag in a_tags:
            href = a_tag["href"]
            job_link = urljoin(url, href)
            
            if job_link in seen_links:
                continue
                
            link_text = a_tag.get_text(separator=' ', strip=True)
            
            # Check if this link is likely a job offer using our job_link_keywords
            is_job_link = False
            for jkw in self.job_link_keywords:
                if re.search(r'\b' + re.escape(jkw) + r'\b', link_text, re.IGNORECASE) or \
                   re.search(r'\b' + re.escape(jkw) + r'\b', href, re.IGNORECASE):
                    is_job_link = True
                    break
                    
            if not is_job_link:
                continue
                
            # Now verify if it matches our actual search keywords (e.g. IT, Python, Werkstudent)
            matched_keyword = None
            for kw in self.keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', link_text, re.IGNORECASE):
                    matched_keyword = kw
                    break
                    
            if matched_keyword:
                jobs.append({
                    "title": self.truncate(link_text, 80),
                    "date": "Generic Page",
                    "link": job_link,
                    "keyword": matched_keyword
                })
                seen_links.add(job_link)
                
        return jobs
