import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper

class StellenwerkScraper(BaseScraper):
    def scrape(self, page, url):
        jobs = []
        page.goto(url)
        
        try:
            page.wait_for_selector("p.text-xl", timeout=10000)
        except:
            print("  [!] Timeout waiting for jobs")
            return jobs

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        title_tags = soup.find_all("p", class_=re.compile("text-xl"))
        
        for title_tag in title_tags:
            title = title_tag.get_text(strip=True)
            a_tag = title_tag.find_parent("a")
            if not a_tag or not a_tag.has_attr("href"):
                continue
                
            href = a_tag["href"]
            job_link = urljoin(url, href)
            
            date = "Unknown"
            date_tag = a_tag.find("p", class_=re.compile("text-right"))
            if date_tag:
                date = date_tag.get_text(strip=True)
                
            card_text = a_tag.get_text(separator=' ', strip=True)
            
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
