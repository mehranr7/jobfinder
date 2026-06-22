import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper

class IndeedScraper(BaseScraper):
    def scrape(self, page, url):
        jobs = []
        try:
            page.goto(url, timeout=20000)
            page.wait_for_selector(".jobsearch-ResultsList", timeout=15000)
        except Exception as e:
            print(f"  [!] Timeout or failed to load: {e}")
            return jobs

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        
        cards = soup.find_all("div", class_=re.compile("job_seen_beacon"))
        if not cards:
            cards = soup.find_all("td", class_="resultContent")
            
        for card in cards:
            title_tag = card.find(["h2", "span"], title=True)
            if not title_tag:
                title_tag = card.find("h2", class_=re.compile("jobTitle"))
                
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
            
            a_tag = card.find("a", href=True)
            if not a_tag:
                a_tag = card.find_parent("a", href=True)
                
            if not a_tag:
                continue
                
            job_link = urljoin(url, a_tag["href"])
            
            date_tag = card.find("span", class_=re.compile("date"))
            date = date_tag.get_text(strip=True) if date_tag else "Unknown"
            date = date.replace("Posted", "").strip()
            
            card_text = card.get_text(separator=' ', strip=True)
            
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
