import sys
import re
import random
import time
from urllib.parse import urljoin
import yaml
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import database
import utils

sys.stdout.reconfigure(encoding='utf-8')

STATE_RUNNING = "RUNNING"
STATE_PAUSED = "PAUSED"
STATE_STOPPED = "STOPPED"
current_state = STATE_RUNNING

def check_state(log_queue=None):
    """
    Checks the current execution state.
    Blocks if PAUSED. Returns False if STOPPED. Returns True if RUNNING.
    """
    global current_state
    was_paused = False
    while current_state == STATE_PAUSED:
        if not was_paused:
            emit_log("\n--- SCRAPER PAUSED ---", log_queue)
            was_paused = True
        time.sleep(0.5)
        
    if was_paused and current_state == STATE_RUNNING:
        emit_log("\n--- SCRAPER RESUMED ---", log_queue)
        
    if current_state == STATE_STOPPED:
        emit_log("\n--- SCRAPER STOPPED BY USER ---", log_queue)
        return False
        
    return True

STELLENWERK_LINK = ""
STELLENWERK_PAGES = 1
STEPSTONE_LINK = ""
STEPSTONE_PAGES = 1
TARGET_URLS = []
KEYWORDS = []
NEGATIVE_KEYWORDS = []
DELAY_MIN_MS = 1500
DELAY_MAX_MS = 3500

def load_config():
    global STELLENWERK_LINK, STELLENWERK_PAGES, STEPSTONE_LINK, STEPSTONE_PAGES
    global TARGET_URLS, KEYWORDS, NEGATIVE_KEYWORDS, DELAY_MIN_MS, DELAY_MAX_MS

    with open("config.yml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    STELLENWERK_LINK = config.get("stellenwerk_link", "")
    STELLENWERK_PAGES = config.get("stellenwerk_pages", 1)
    STEPSTONE_LINK = config.get("stepstone_link", "")
    STEPSTONE_PAGES = config.get("stepstone_pages", 1)

    urls = []
    if STELLENWERK_LINK:
        sep = "&" if "?" in STELLENWERK_LINK else "?"
        for i in range(STELLENWERK_PAGES):
            offset = i * 10
            urls.append({
                "url": f"{STELLENWERK_LINK}{sep}pagination%5Bstart%5D={offset}",
                "domain": "Stellenwerk",
                "page": i + 1
            })
            
    if STEPSTONE_LINK:
        urls.append({
            "url": STEPSTONE_LINK,
            "domain": "Stepstone",
            "page": 1
        })
        for i in range(2, STEPSTONE_PAGES + 1):
            if "?" in STEPSTONE_LINK:
                parts = STEPSTONE_LINK.split("?", 1)
                urls.append({
                    "url": f"{parts[0]}?page={i}&{parts[1]}",
                    "domain": "Stepstone",
                    "page": i
                })
            else:
                urls.append({
                    "url": f"{STEPSTONE_LINK}?page={i}",
                    "domain": "Stepstone",
                    "page": i
                })
                
    TARGET_URLS = urls
    KEYWORDS = config.get("keywords", [])
    NEGATIVE_KEYWORDS = config.get("negative_keywords", [])
    DELAY_MIN_MS = config.get("delay_min_ms", 1500)
    DELAY_MAX_MS = config.get("delay_max_ms", 3500)



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
            date_raw = date_tag.get_text(strip=True)
            date = utils.parse_relative_date(date_raw)
            
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
                "company": "Stellenwerk",
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
        date_raw = time_tag.get_text(strip=True) if time_tag else "Unknown"
        date = utils.parse_relative_date(date_raw)
        
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
                "company": "Stepstone",
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords)
            })
    return jobs

def emit_log(msg, log_queue=None):
    """
    Prints a message to the console and pushes it to the log_queue if provided.
    """
    print(msg)
    if log_queue is not None:
        log_queue.put(msg)

def main(log_queue=None):
    """
    Main execution loop.
    Initializes the Playwright headless browser, loops through configured URLs,
    extracts the jobs using the appropriate parser, deep-scrapes the descriptions,
    and inserts them into the SQLite database.
    """
    global current_state
    current_state = STATE_RUNNING
    
    load_config()
    database.init_db()
    
    # Sort URLs alphabetically to group them by domain in the console output
    sorted_urls = sorted(TARGET_URLS, key=lambda x: (x["domain"], x["page"]))
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        
        current_domain = ""
        
        emit_log("--- SCRAPING STARTED ---", log_queue)
        
        for target in sorted_urls:
            if not check_state(log_queue):
                break
                
            url = target["url"]
            domain_name = target["domain"]
            page_num = target["page"]
            
            jobs = []
            
            if domain_name != current_domain:
                emit_log(f"\n[ {domain_name} ]", log_queue)
                current_domain = domain_name

            if domain_name == "Stellenwerk":
                jobs = scrape_stellenwerk(page, url)
            elif domain_name == "Stepstone":
                jobs = scrape_stepstone(page, url)
            else:
                emit_log(f"Unknown domain for URL: {url}", log_queue)
                continue
                
            total_jobs = len(jobs)
            new_jobs = 0
            for i, job in enumerate(jobs):
                if not check_state(log_queue):
                    break
                    
                if database.job_exists(job['link']):
                    continue
                
                new_jobs += 1
                title_disp = utils.truncate(job['title'], 50)
                
                kw_disp = utils.truncate(job['keyword'], 20)
                if job['negative_keyword']:
                    kw_disp += f" (Neg: {utils.truncate(job['negative_keyword'], 10)})"
                
                # Build progress string without carriage returns for the web UI
                progress = int(50 * (i + 1) / total_jobs) if total_jobs > 0 else 0
                bar = "█" * progress + "-" * (50 - progress)
                
                log_msg = f"  -> NEW Match: {job['date']:>12} | {kw_disp:<35} | {title_disp}\n"
                log_msg += f"  -> Progress: [{bar}] {i+1}/{total_jobs}"
                
                emit_log(log_msg, log_queue)
                
                # Deep Scrape
                try:
                    page.goto(job['link'], timeout=15000)
                    page.wait_for_load_state("domcontentloaded")
                    html = page.content()
                    job['description'] = utils.clean_text(html)
                    
                    desc_tags = []
                    for kw in KEYWORDS:
                        if re.search(r'\b' + re.escape(kw) + r'\b', job['description'], re.IGNORECASE):
                            desc_tags.append(kw)
                    # Deduplicate while preserving order
                    seen = set()
                    unique_tags = [x for x in desc_tags if not (x in seen or seen.add(x))]
                    job['description_tags'] = ", ".join(unique_tags)
                except Exception as e:
                    job['description'] = "Failed to extract content."
                    job['description_tags'] = ""
                    
                # Insert into DB
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(r'\b' + re.escape(nkw) + r'\b', card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": date,
                "link": job_link,
                "company": "Stellenwerk",
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
        date_raw = time_tag.get_text(strip=True) if time_tag else "Unknown"
        date = utils.parse_relative_date(date_raw)
        
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
                "company": "Stepstone",
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords)
            })
    return jobs

def emit_log(msg, log_queue=None):
    """
    Prints a message to the console and pushes it to the log_queue if provided.
    """
    print(msg)
    if log_queue is not None:
        log_queue.put(msg)

def main(log_queue=None):
    """
    Main execution loop.
    Initializes the Playwright headless browser, loops through configured URLs,
    extracts the jobs using the appropriate parser, deep-scrapes the descriptions,
    and inserts them into the SQLite database.
    """
    global current_state
    current_state = STATE_RUNNING
    
    load_config()
    database.init_db()
    
    # Sort URLs alphabetically to group them by domain in the console output
    sorted_urls = sorted(TARGET_URLS, key=lambda x: (x["domain"], x["page"]))
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        
        current_domain = ""
        
        emit_log("--- SCRAPING STARTED ---", log_queue)
        
        for target in sorted_urls:
            if not check_state(log_queue):
                break
                
            url = target["url"]
            domain_name = target["domain"]
            page_num = target["page"]
            
            jobs = []
            
            if domain_name != current_domain:
                emit_log(f"\n[ {domain_name} ]", log_queue)
                current_domain = domain_name

            if domain_name == "Stellenwerk":
                jobs = scrape_stellenwerk(page, url)
            elif domain_name == "Stepstone":
                jobs = scrape_stepstone(page, url)
            else:
                emit_log(f"Unknown domain for URL: {url}", log_queue)
                continue
                
            total_jobs = len(jobs)
            new_jobs = 0
            for i, job in enumerate(jobs):
                if not check_state(log_queue):
                    break
                    
                if database.job_exists(job['link']):
                    continue
                
                new_jobs += 1
                title_disp = utils.truncate(job['title'], 50)
                
                kw_disp = utils.truncate(job['keyword'], 20)
                if job['negative_keyword']:
                    kw_disp += f" (Neg: {utils.truncate(job['negative_keyword'], 10)})"
                
                # Build progress string without carriage returns for the web UI
                progress = int(50 * (i + 1) / total_jobs) if total_jobs > 0 else 0
                bar = "█" * progress + "-" * (50 - progress)
                
                log_msg = f"  -> NEW Match: {job['date']:>12} | {kw_disp:<35} | {title_disp}\n"
                log_msg += f"  -> Progress: [{bar}] {i+1}/{total_jobs}"
                
                emit_log(log_msg, log_queue)
                
                # Deep Scrape
                try:
                    page.goto(job['link'], timeout=15000)
                    page.wait_for_load_state("domcontentloaded")
                    html = page.content()
                    job['description'] = utils.clean_text(html)
                    
                    desc_tags = []
                    for kw in KEYWORDS:
                        if re.search(r'\b' + re.escape(kw) + r'\b', job['description'], re.IGNORECASE):
                            desc_tags.append(kw)
                    # Deduplicate while preserving order
                    seen = set()
                    unique_tags = [x for x in desc_tags if not (x in seen or seen.add(x))]
                    job['description_tags'] = ", ".join(unique_tags)
                except Exception as e:
                    job['description'] = "Failed to extract content."
                    job['description_tags'] = ""
                    
                # Insert into DB
                database.insert_job(job)
                
                # Slight delay between deep scrapes to avoid getting blocked
                page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
                
            if total_jobs > 0:
                emit_log(f"  -> P.{page_num} - Found {total_jobs} total jobs. Deep scraped {new_jobs} new jobs.", log_queue)
                
            # Slight delay between domain pages
            page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
            
            if current_state == STATE_STOPPED:
                break
                
        browser.close()
        
    emit_log("\n--- SCRAPING FINISHED ---", log_queue)
        
    if log_queue is not None:
        log_queue.put("DONE")

if __name__ == "__main__":
    main()
