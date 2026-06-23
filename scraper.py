import sys
import re
import random
from datetime import datetime
from urllib.parse import urljoin
import yaml
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TARGET_URLS = config.get("target_urls", [])
KEYWORDS = config.get("keywords", [])
NEGATIVE_KEYWORDS = config.get("negative_keywords", [])
DELAY_MIN_MS = config.get("delay_min_ms", 1500)
DELAY_MAX_MS = config.get("delay_max_ms", 3500)

def truncate(s, length=60):
    return s if len(s) <= length else s[:length-3] + "..."

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

def scrape_stellenwerk(page, url):
    """
    Scrapes job offers from a Stellenwerk URL using Playwright.
    Extracts the title, date, and link, and filters by defined keywords.
    """
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
        
        matched_keywords = []
        for kw in KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', card_text, re.IGNORECASE):
                matched_keywords.append(kw)
                
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(r'\b' + re.escape(nkw) + r'\b', card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": date,
                "link": job_link,
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords)
            })
    return jobs



def scrape_stepstone(page, url):
    """
    Scrapes job offers from a Stepstone URL using Playwright.
    Extracts jobs listed inside 'article' tags.
    """
    jobs = []
    page.goto(url)
    
    try:
        page.wait_for_selector("article", timeout=15000)
    except:
        print("  [!] Timeout / Blocked")
        return jobs

    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    
    articles = soup.find_all("article")
    
    for article in articles:
        job_a_tag = None
        # First, try to find the specific job link format
        for a in article.find_all("a", href=True):
            if "stellenangebote--" in a["href"]:
                job_a_tag = a
                break
                
        # Fallback: check if h2 contains or is wrapped in an a_tag
        if not job_a_tag:
            h2 = article.find("h2")
            if h2:
                if h2.find("a", href=True):
                    job_a_tag = h2.find("a", href=True)
                elif h2.parent.name == "a":
                    job_a_tag = h2.parent
                    
        # Last resort: take the first link
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
        
        matched_keywords = []
        for kw in KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', card_text, re.IGNORECASE):
                matched_keywords.append(kw)
                
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(r'\b' + re.escape(nkw) + r'\b', card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": date,
                "link": job_link,
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords)
            })
    return jobs

def generate_report(jobs, quiet=False):
    """
    Generates a static HTML report (results.html) from the scraped jobs list.
    It reads 'report_template.html' and injects the job cards dynamically.
    """
    with open("report_template.html", "r", encoding="utf-8") as f:
        template = f.read()
        
    jobs_html = '<div class="jobs-container">\n'
    for i, job in enumerate(jobs):
        escaped_desc = job['description'].replace('<', '&lt;').replace('>', '&gt;')
        
        pos_badges = "".join([f'<span class="keyword-badge">{k.strip()}</span>' for k in job['keyword'].split(',') if k.strip()])
        neg_badges = "".join([f'<span class="keyword-badge negative-badge">{k.strip()}</span>' for k in job['negative_keyword'].split(',') if k.strip()])
        all_badges = pos_badges + neg_badges
        
        # We store the comma separated keywords in data-keyword to be parsed by Javascript
        data_keywords = job['keyword'].lower()
        if job['negative_keyword']:
             data_keywords += ", " + job['negative_keyword'].lower()
             
        jobs_html += f"""
        <div class="job-card" data-title="{job['title'].lower()}" data-keyword="{data_keywords}" data-url="{job['link']}" data-index="{i}">
            <h2 class="job-title">{job['title']}</h2>
            <div class="job-meta">
                <span><strong>Date:</strong> {job['date']}</span> | 
                <span><strong>Keywords:</strong> {all_badges}</span> | 
                <span><strong>Link:</strong> <a href="{job['link']}" target="_blank">{job['link']}</a></span>
            </div>
            <div class="desc-header">
                <strong>Description:</strong>
                <div>
                    <button class="done-btn" onclick="toggleDone(this)">✓ Mark as Done</button>
                    <button class="copy-btn" onclick="copyToClipboard('desc-{i}', this)">Copy</button>
                </div>
            </div>
            <div class="job-description" id="desc-{i}">{escaped_desc}</div>
        </div>
        """
    jobs_html += '</div>'
        
    html = template.replace("{{timestamp}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    html = html.replace("{{jobs_html}}", jobs_html)
    
    with open("results.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    if not quiet:
        print(f"\n--- SUCCESS ---")
        print(f"Report generated: results.html with {len(jobs)} jobs.")

def main():
    """
    Main execution loop.
    Initializes the Playwright headless browser, loops through configured URLs,
    extracts the jobs using the appropriate parser, deep-scrapes the descriptions,
    and finally writes the results.html report.
    """
    matched_jobs = []
    
    # Sort URLs alphabetically to group them by domain in the console output
    sorted_urls = sorted(TARGET_URLS)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        
        current_domain = ""
        
        for url in sorted_urls:
            jobs = []
            
            if "stellenwerk" in url:
                domain_name = "Stellenwerk"
            elif "stepstone" in url:
                domain_name = "Stepstone"
            else:
                domain_name = "Unknown"
                
            if domain_name != current_domain:
                print(f"\n[ {domain_name} ]")
                current_domain = domain_name

            if "stellenwerk" in url:
                jobs = scrape_stellenwerk(page, url)
            elif "stepstone" in url:
                jobs = scrape_stepstone(page, url)
            else:
                print(f"Unknown domain for URL: {url}")
                continue
                
            total_jobs = len(jobs)
            for i, job in enumerate(jobs):
                title_disp = truncate(job['title'], 50)
                
                
                # Clear progress bar before printing new match
                sys.stdout.write("\r" + " " * 100 + "\r")
                kw_disp = truncate(job['keyword'], 20)
                if job['negative_keyword']:
                    kw_disp += f" (Neg: {truncate(job['negative_keyword'], 10)})"
                print(f"  -> Match: {job['date']:>12} | {kw_disp:<35} | {title_disp}")
                
                # Draw progress bar
                progress = int(50 * (i + 1) / total_jobs) if total_jobs > 0 else 0
                bar = "█" * progress + "-" * (50 - progress)
                sys.stdout.write(f"\r  -> Progress: [{bar}] {i+1}/{total_jobs}")
                sys.stdout.flush()
                
                # Deep Scrape
                try:
                    page.goto(job['link'], timeout=15000)
                    page.wait_for_load_state("domcontentloaded")
                    html = page.content()
                    job['description'] = clean_text(html)
                except Exception as e:
                    job['description'] = "Failed to extract content."
                    
                matched_jobs.append(job)
                
                # Live update the report on each item
                generate_report(matched_jobs, quiet=True)
                
                # Slight delay between deep scrapes to avoid getting blocked
                page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
                
            if total_jobs > 0:
                sys.stdout.write("\r" + " " * 100 + "\r")
                print(f"  -> Completed deep scraping {total_jobs} jobs.")
                
            # Slight delay between domain pages
            page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
                
        browser.close()
        
    generate_report(matched_jobs)

if __name__ == "__main__":
    main()
