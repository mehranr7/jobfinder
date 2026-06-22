import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper

class StepstoneScraper(BaseScraper):
    def scrape(self, page, url):
        jobs = []
        try:
            page.goto(url, timeout=20000)
            page.wait_for_selector("article", timeout=15000)
        except Exception as e:
            print(f"  [!] Timeout or failed to load: {e}")
            return jobs

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        articles = soup.find_all("article")
        
        for article in articles:
            job_a_tag = None
            for a in article.find_all("a", href=True):
                if "stellenangebote--" in a["href"]:
                    job_a_tag = a
                    break
                    
            if not job_a_tag:
                h2 = article.find("h2")
                if h2:
                    if h2.find("a", href=True):
                        job_a_tag = h2.find("a", href=True)
                    elif h2.parent.name == "a":
                        job_a_tag = h2.parent
                        
            if not job_a_tag:
                job_a_tag = article.find("a", href=True)
                
            if not job_a_tag:
                continue
                
            h2 = article.find("h2")
            title = h2.get_text(strip=True) if h2 else job_a_tag.get_text(strip=True)
            
            job_link = urljoin(url, job_a_tag["href"])
            
            time_tag = article.find("time")
            date = time_tag.get_text(strip=True) if time_tag else "Unknown"
            
            card_text = article.get_text(separator=' ', strip=True)
            
            matched_keyword = None
            for kw in self.keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', card_text, re.IGNORECASE):
                    matched_keyword = kw
                    break
                    
            if matched_keyword:
                jobs.append({
                    "title": title,
                    "date": date,
                    "link": job_link,
                    "keyword": matched_keyword
                })
        return jobs
