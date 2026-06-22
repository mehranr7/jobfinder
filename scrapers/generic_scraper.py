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
        Detects if the current page is a career portal based on UI filter keywords AND job titles.
        Uses JavaScript evaluation to pierce Shadow DOMs so it can see hidden text.
        Needs at least 6 matching indicator keywords to be strict.
        """
        js_code = '''
        () => {
            function extractText(node) {
                let text = '';
                if (node.nodeType === Node.TEXT_NODE) {
                    return node.textContent + ' ';
                }
                if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.shadowRoot) {
                        text += extractText(node.shadowRoot);
                    }
                    for (let child of node.childNodes) {
                        text += extractText(child);
                    }
                }
                return text;
            }
            return extractText(document.body);
        }
        '''
        text = page.evaluate(js_code).lower()
        
        matches = 0
        all_indicators = self.portal_indicator_keywords + self.keywords
        for ind in all_indicators:
            if re.search(r'\b' + re.escape(ind.lower()) + r'\b', text):
                matches += 1
                if matches >= 6:
                    return True
        return False

    def get_links_matching_keywords(self, page, url, keyword_list):
        """
        Extracts and resolves hrefs from a_tags that match any keyword in the given list.
        Uses JavaScript evaluation to pierce Shadow DOMs to find hidden links.
        """
        js_code = '''
        () => {
            function extractLinks(node) {
                let links = [];
                if (node.nodeType === Node.ELEMENT_NODE) {
                    if (node.tagName === 'A' && node.href) {
                        links.push({text: node.innerText || node.textContent || '', href: node.href});
                    }
                    if (node.shadowRoot) {
                        links = links.concat(extractLinks(node.shadowRoot));
                    }
                    for (let child of node.childNodes) {
                        links = links.concat(extractLinks(child));
                    }
                }
                return links;
            }
            return extractLinks(document.body);
        }
        '''
        extracted_links = page.evaluate(js_code)
        
        links = []
        for l in extracted_links:
            href = l['href']
            link_text = l['text'].strip()
            
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
            page.wait_for_timeout(5000)
            
            # Extract job links using BOTH job_link_keywords AND the user's main keywords
            combined_keywords = self.keywords + self.job_link_keywords
            found_links = self.get_links_matching_keywords(page, base_url, combined_keywords)
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
                page.wait_for_timeout(6000)
            except Exception as e:
                print(f"  [!] Failed to load {current_url}: {e}")
                continue
                
            # Is this the portal?
            if self.is_career_portal(page):
                print("  -> [+] Career Portal Detected! Extracting jobs...")
                extracted = self.scrape_career_portal(page, current_url)
                jobs.extend(extracted)
                
            # Always enqueue navigation links if under max depth
            if depth < self.max_depth:
                nav_links = self.get_links_matching_keywords(page, current_url, self.navigation_keywords)
                
                # Extract core brand name (e.g. 'adesso') to avoid crawling facebook/linkedin
                from urllib.parse import urlparse
                base_netloc = urlparse(start_url).netloc.replace("www.", "")
                brand_name = base_netloc.split('.')[0] if '.' in base_netloc else base_netloc
                
                for _, nav_url in nav_links:
                    # Prevent revisiting or crawling massive external sites
                    if nav_url not in visited and nav_url.startswith("http"):
                        # Ensure we stay on the company's domains (e.g. jobs.adesso-group.com or adesso.de)
                        parsed_nav = urlparse(nav_url)
                        if brand_name in parsed_nav.netloc.lower():
                            visited.add(nav_url)
                            queue.append((nav_url, depth + 1))
                            
        return jobs
