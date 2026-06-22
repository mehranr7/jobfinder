import re
from collections import deque
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper

class GenericScraper(BaseScraper):
    def __init__(self, keywords, delay_min_ms, delay_max_ms, job_link_keywords, max_depth, navigation_keywords, portal_indicator_keywords, pagination_keywords):
        super().__init__(keywords, delay_min_ms, delay_max_ms)
        self.job_link_keywords = job_link_keywords
        self.max_depth = max_depth
        self.navigation_keywords = navigation_keywords
        self.portal_indicator_keywords = portal_indicator_keywords
        self.pagination_keywords = pagination_keywords

    def is_career_portal(self, page):
        """
        Detects if the current page is a career portal based on UI filter keywords.
        Needs at least 2 matching indicator keywords.
        """
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ', strip=True).lower()
        
        matches = 0
        for ind in self.portal_indicator_keywords:
            if re.search(r'\b' + re.escape(ind.lower()) + r'\b', text):
                matches += 1
                if matches >= 2:
                    return True
        return False

    def get_links_matching_keywords(self, soup, url, keyword_list):
        """
        Extracts and resolves hrefs from a_tags that match any keyword in the given list.
        """
        links = []
        a_tags = soup.find_all("a", href=True)
        for a_tag in a_tags:
            href = a_tag["href"]
            link_text = a_tag.get_text(separator=' ', strip=True)
            
            for kw in keyword_list:
                if re.search(r'\b' + re.escape(kw) + r'\b', link_text, re.IGNORECASE) or \
                   re.search(r'\b' + re.escape(kw) + r'\b', href, re.IGNORECASE):
                    links.append((link_text, urljoin(url, href)))
                    break
        return links

    def click_pagination(self, page):
        """
        Looks for a pagination "Next" or "Load More" button and clicks it.
        Returns True if clicked, False if not found.
        """
        # Try to find a link or button matching pagination keywords
        for kw in self.pagination_keywords:
            try:
                # Use a case-insensitive xpath search for links or buttons
                selector = f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw.lower()}')] | //button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{kw.lower()}')]"
                element = page.locator(selector).first
                if element.is_visible():
                    element.click()
                    return True
            except:
                pass
        return False

    def scrape_career_portal(self, page, base_url):
        """
        Scrapes all job links from the portal, handling pagination.
        """
        all_job_links = {}
        pages_scraped = 0
        max_pages = 10
        
        while pages_scraped < max_pages:
            pages_scraped += 1
            
            # Wait for any dynamic content
            page.wait_for_timeout(3000)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract job links
            found_links = self.get_links_matching_keywords(soup, base_url, self.job_link_keywords)
            for link_text, job_url in found_links:
                if job_url not in all_job_links:
                    all_job_links[job_url] = link_text
                    
            # Try to click next
            if not self.click_pagination(page):
                break
                
        # Now we filter against our target job keywords (e.g. IT, Python, Werkstudent)
        jobs = []
        for job_url, link_text in all_job_links.items():
            matched_keyword = None
            for kw in self.keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', link_text, re.IGNORECASE):
                    matched_keyword = kw
                    break
                    
            if matched_keyword:
                jobs.append({
                    "title": self.truncate(link_text, 80),
                    "date": "Generic Page",
                    "link": job_url,
                    "keyword": matched_keyword
                })
                
        return jobs

    def scrape(self, page, start_url):
        """
        Autonomous BFS navigation crawler to find the career portal and scrape it.
        """
        jobs = []
        queue = deque([(start_url, 0)])
        visited = set([start_url])
        
        while queue:
            current_url, depth = queue.popleft()
            
            print(f"  -> Navigating to {current_url} (Depth {depth})")
            try:
                page.goto(current_url, timeout=20000)
                # Wait a bit for dynamic React/Vue apps
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"  [!] Failed to load {current_url}: {e}")
                continue
                
            # Is this the portal?
            if self.is_career_portal(page):
                print("  -> [+] Career Portal Detected! Extracting jobs...")
                jobs = self.scrape_career_portal(page, current_url)
                break
            else:
                # Not a portal, enqueue navigation links if under max depth
                if depth < self.max_depth:
                    html = page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    nav_links = self.get_links_matching_keywords(soup, current_url, self.navigation_keywords)
                    
                    for _, nav_url in nav_links:
                        # Prevent revisiting or crawling massive external sites
                        if nav_url not in visited and nav_url.startswith("http"):
                            visited.add(nav_url)
                            queue.append((nav_url, depth + 1))
                            
        return jobs
