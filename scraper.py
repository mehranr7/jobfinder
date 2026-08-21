import os
import re
import sys
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import database
import utils
from public_sources import PUBLIC_SOURCES
from source_registry import SourceAdapter, build_targets, load_private_sources, set_query_parameter

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
            emit_log("⏸ Scraper paused", log_queue)
            was_paused = True
        time.sleep(0.5)
        
    if was_paused and current_state == STATE_RUNNING:
        emit_log("▶ Scraper resumed", log_queue)
        
    if current_state == STATE_STOPPED:
        emit_log("⏹ Scraper stopped", log_queue)
        return False
        
    return True

TARGET_URLS = []
SOURCE_ADAPTERS = {}
KEYWORDS = []
NEGATIVE_KEYWORDS = []
DELAY_MIN_MS = 1500
DELAY_MAX_MS = 3500
BLOCK_HEAVY_RESOURCES = True

def load_config():
    global TARGET_URLS, SOURCE_ADAPTERS, KEYWORDS, NEGATIVE_KEYWORDS
    global DELAY_MIN_MS, DELAY_MAX_MS, BLOCK_HEAVY_RESOURCES

    config = utils.load_config()

    adapters = [
        *_legacy_sources(),
        *PUBLIC_SOURCES,
        *load_private_sources(os.path.dirname(__file__)),
    ]
    SOURCE_ADAPTERS = {adapter.name: adapter for adapter in adapters}
    TARGET_URLS = build_targets(config, adapters)
    KEYWORDS = config.get("keywords", [])
    NEGATIVE_KEYWORDS = config.get("negative_keywords", [])
    DELAY_MIN_MS = config.get("delay_min_ms", 1500)
    DELAY_MAX_MS = config.get("delay_max_ms", 3500)
    BLOCK_HEAVY_RESOURCES = config.get("block_heavy_resources", True)

def scrape_stellenwerk(page, url):
    """
    Scrapes job offers from a Stellenwerk URL using Playwright.
    Extracts the title, date, and link, and filters by defined keywords.
    """
    jobs = []
    try:
        page.goto(url)
    except Exception as e:
        print(f"  [!] Failed to load URL: {e}")
        return jobs
    
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
        
        company = "Stellenwerk"
        building_svg = a_tag.find("svg", class_=re.compile("lucide-building-2"))
        if building_svg and building_svg.parent:
            company_text = building_svg.parent.get_text(strip=True)
            if company_text:
                company = company_text
                
        matched_keywords = []
        for kw in KEYWORDS:
            if re.search(re.escape(kw), title, re.IGNORECASE):
                matched_keywords.append(kw)
                
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(re.escape(nkw), card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": date,
                "link": job_link,
                "company": company,
                "platform": "Stellenwerk",
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords),
                "preview_text": card_text
            })
    return jobs

def scrape_stepstone(page, url):
    """
    Scrapes job offers from a Stepstone URL.
    Extracts jobs listed inside 'article' tags.
    """
    import requests
    jobs = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  [!] Failed to load URL via requests: {e}")
        return jobs

    soup = BeautifulSoup(html, 'html.parser')
    
    articles = soup.find_all("article")
    
    for article in articles:
        job_a_tag = None
        # First, try to find the specific job link format
        for a in article.find_all("a", href=True):
            if "stellenangebote--" in a["href"] or "/job/" in a["href"] or "job-item" in a.get("class", []):
                job_a_tag = a
                break
                
        if not job_a_tag:
            continue
            
        h2 = article.find("h2")
        title = h2.get_text(strip=True) if h2 else job_a_tag.get_text(strip=True)
        
        raw_link = urljoin(url, job_a_tag["href"])
        job_link = raw_link.split('?')[0]
        
        time_tag = article.find("time")
        date_raw = time_tag.get_text(strip=True) if time_tag else "Unknown"
        date = utils.parse_relative_date(date_raw)
        
        card_text = article.get_text(separator=' ', strip=True)
        if not card_text:
            continue
            
        company_tag = article.find(attrs={"data-at": "job-item-company-name"})
        company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"
        
        matched_keywords = []
        for kw in KEYWORDS:
            if re.search(re.escape(kw), title, re.IGNORECASE):
                matched_keywords.append(kw)
                
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(re.escape(nkw), card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": date,
                "link": job_link,
                "company": company,
                "platform": "Stepstone",
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords),
                "preview_text": card_text
            })
    return jobs

def scrape_xing(page, url):
    """
    Scrapes job offers from a Xing URL.
    Extracts jobs listed inside 'article' tags.
    """
    import requests
    jobs = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  [!] Failed to load Xing URL via requests: {e}")
        return jobs

    soup = BeautifulSoup(html, 'html.parser')
    
    articles = soup.find_all("article")
    
    for article in articles:
        job_a_tag = article.find("a", href=True)
                
        if not job_a_tag:
            continue
            
        h2 = article.find("h2")
        title = h2.get_text(strip=True) if h2 else job_a_tag.get_text(strip=True)
        
        raw_link = urljoin("https://www.xing.com", job_a_tag["href"])
        job_link = raw_link.split('?')[0]
        
        card_text = article.get_text(separator=' ', strip=True)
        if not card_text:
            continue
            
        company_tag = article.find("p")
        company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"
        
        matched_keywords = []
        for kw in KEYWORDS:
            if re.search(re.escape(kw), title, re.IGNORECASE):
                matched_keywords.append(kw)
                
        matched_negative_keywords = []
        for nkw in NEGATIVE_KEYWORDS:
            if re.search(re.escape(nkw), card_text, re.IGNORECASE):
                matched_negative_keywords.append(nkw)
                
        if matched_keywords:
            jobs.append({
                "title": title,
                "date": "Unknown",
                "link": job_link,
                "company": company,
                "platform": "Xing",
                "keyword": ", ".join(matched_keywords),
                "negative_keyword": ", ".join(matched_negative_keywords),
                "preview_text": card_text
            })
    return jobs


def _first_page_then_query(parameter, value_for_page=lambda page_number: page_number):
    def builder(url, page_number):
        if page_number == 1 and parameter != "pagination[start]":
            return url
        return set_query_parameter(url, parameter, value_for_page(page_number))

    return builder


def _legacy_sources():
    """Expose existing scrapers through the same adapter contract as new sources."""

    return (
        SourceAdapter(
            name="Stellenwerk",
            link_key="stellenwerk_link",
            pages_key="stellenwerk_pages",
            page_url=_first_page_then_query(
                "pagination[start]", lambda page_number: (page_number - 1) * 10
            ),
            scrape=lambda page, url, keywords, negative_keywords: scrape_stellenwerk(page, url),
        ),
        SourceAdapter(
            name="Stepstone",
            link_key="stepstone_link",
            pages_key="stepstone_pages",
            page_url=_first_page_then_query("page"),
            scrape=lambda page, url, keywords, negative_keywords: scrape_stepstone(page, url),
        ),
        SourceAdapter(
            name="Xing",
            link_key="xing_link",
            pages_key="xing_pages",
            page_url=_first_page_then_query("page"),
            scrape=lambda page, url, keywords, negative_keywords: scrape_xing(page, url),
        ),
    )

def emit_log(msg, log_queue=None, max_len=105):
    """
    Formats a single-line message with timestamp [HH:MM:SS] and character limit,
    prints to console and pushes to log_queue.
    """
    if str(msg) == "  -> UI_RELOAD" or str(msg) == "DONE":
        if log_queue is not None:
            log_queue.put(msg)
        return

    # Strip newlines and excess whitespace so every message is strictly 1 clean line
    clean = " ".join(str(msg).replace("\r", " ").replace("\n", " ").split())
    if not clean:
        return
    if len(clean) > max_len:
        clean = clean[:max_len - 3] + "..."

    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {clean}"

    try:
        print(formatted, flush=True)
    except Exception:
        try:
            print(formatted.encode(getattr(sys.stdout, 'encoding', 'ascii') or 'ascii', errors='replace').decode(getattr(sys.stdout, 'encoding', 'ascii') or 'ascii'), flush=True)
        except Exception:
            pass
    if log_queue is not None:
        log_queue.put(formatted)

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
        if BLOCK_HEAVY_RESOURCES:
            page.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"font", "image", "media"}
                else route.continue_(),
            )
        
        current_domain = ""
        
        emit_log("🚀 Scraper started", log_queue)
        
        for target in sorted_urls:
            if not check_state(log_queue):
                break
                
            url = target["url"]
            domain_name = target["domain"]
            page_num = target["page"]
            
            jobs = []
            
            if domain_name != current_domain:
                emit_log(f"🌐 [{domain_name}] Starting scrape...", log_queue)
                current_domain = domain_name

            adapter = SOURCE_ADAPTERS.get(domain_name)
            if adapter is None:
                emit_log(f"  ⚠ Unknown domain adapter: {domain_name}", log_queue)
                continue

            try:
                jobs = adapter.scrape(page, url, KEYWORDS, NEGATIVE_KEYWORDS)
            except Exception as exc:
                emit_log(f"  ✖ {domain_name} listing failed: {str(exc)[:40]}", log_queue)
                continue
                
            total_jobs = len(jobs)
            new_jobs = 0
            for i, job in enumerate(jobs):
                if not check_state(log_queue):
                    break
                    
                title_disp = utils.truncate(job['title'], 40)
                    
                if database.job_exists(job['link']):
                    emit_log(f"  ↪ [In DB] {title_disp} [{i+1}/{total_jobs}]", log_queue)
                    continue

                existing_job = database.get_existing_job_by_title_and_company(job['title'], job['company'])
                if existing_job:
                    emit_log(f"  ↪ [Dup on {existing_job['platform']}] {title_disp} ({job.get('company', '')[:15]}) [{i+1}/{total_jobs}]", log_queue)
                    continue
                
                new_jobs += 1
                emit_log(f"  ✨ [NEW] {title_disp} ({job.get('company', '')[:18]}) [{i+1}/{total_jobs}]", log_queue)
                
                # Deep Scrape
                try:
                    text_content = None
                    if adapter.fetch_description is not None:
                        text_content = adapter.fetch_description(job)


                    if not text_content:
                        if adapter.navigate_to_detail:
                            try:
                                response = page.goto(
                                    job.get('_detail_url', job['link']),
                                    timeout=20000,
                                    wait_until='domcontentloaded'
                                )
                            except Exception as goto_err:
                                print(f"Goto error (proceeding to extract anyway): {goto_err}")
                                response = None

                            if response is not None and response.status >= 400:
                                raise ValueError(f"Detail page returned HTTP {response.status}")

                            page.wait_for_timeout(1500) # Wait for dynamic content to load
                        if adapter.extract_description is not None:
                            text_content = adapter.extract_description(page, job)
                        if not text_content:
                            text_content = page.locator('body').inner_text()

                    if len(text_content) < 150:
                        raise ValueError("Extracted text is too short, falling back.")
                        
                    job['description'] = utils.clean_text(text_content) # Just for extra safety with spacing
                    
                    # --- Platform-Specific Description Trimming ---
                    if 'stellenwerk' in job['link'].lower():
                        desc = job['description']
                        start_idx = desc.find('Magazin\n')
                        if start_idx != -1:
                            desc = desc[start_idx + 8:] # cut out Magazin\n
                            
                        # Further trim the repetitive title, company, and 'Dein Job' heading
                        dein_job_idx = desc.find('Dein Job\n')
                        if dein_job_idx != -1:
                            desc = desc[dein_job_idx + 9:] # cut out Dein Job\n
                        
                        end_idx = desc.find('\nJetzt bewerben')
                        if end_idx != -1:
                            desc = desc[:end_idx]
                        
                        job['description'] = desc.strip()
                        
                    elif 'stepstone' in job['link'].lower():
                        desc = job['description']
                        
                        # Remove leading "Ich bin interessiert" and "Speichern" and "Einleitung"
                        prefixes_to_remove = ["Ich bin interessiert", "Speichern", "Einleitung"]
                        lines = desc.split('\n')
                        while lines and (lines[0].strip() in prefixes_to_remove or not lines[0].strip()):
                            lines.pop(0)
                        desc = '\n'.join(lines)
                        
                        t_str = job['title'] + '\n'
                        idx1 = desc.find(t_str)
                        if idx1 != -1:
                            idx2 = desc.find(t_str, idx1 + len(t_str))
                            if idx2 != -1:
                                nl1 = desc.find('\n', idx2 + len(t_str))
                                if nl1 != -1:
                                    desc = desc[nl1 + 1:]
                        
                        end_idx = desc.find('Diese Jobs waren bei anderen Jobsuchenden beliebt')
                        if end_idx != -1:
                            desc = desc[:end_idx]
                        
                        job['description'] = desc.strip()
                        
                    elif 'xing' in job['link'].lower():
                        # Extract the correct date if it's currently Unknown
                        if job['date'] == "Unknown":
                            time_loc = page.locator('time').first
                            if time_loc.count() > 0:
                                dt = time_loc.get_attribute('datetime')
                                if dt:
                                    job['date'] = dt.split('T')[0]
                                    
                        desc = job['description']
                        start_marker = "Über diesen Job"
                        start_idx = desc.find(start_marker)
                        if start_idx != -1:
                            desc = desc[start_idx + len(start_marker):]
                            
                        end_marker = "Unternehmens-Details"
                        end_idx = desc.find(end_marker)
                        if end_idx != -1:
                            desc = desc[:end_idx]
                            
                        job['description'] = desc.strip()
                    # ----------------------------------------------
                    
                    desc_tags = []
                    for kw in KEYWORDS:
                        if re.search(re.escape(kw), job['description'], re.IGNORECASE):
                            desc_tags.append(kw)
                    # Deduplicate while preserving order
                    seen = set()
                    unique_tags = [x for x in desc_tags if not (x in seen or seen.add(x))]
                    job['description_tags'] = ", ".join(unique_tags)
                    
                    neg_desc_tags = []
                    for nkw in NEGATIVE_KEYWORDS:
                        if re.search(re.escape(nkw), job['description'], re.IGNORECASE):
                            neg_desc_tags.append(nkw)
                    # Deduplicate while preserving order
                    seen_neg = set()
                    unique_neg_tags = [x for x in neg_desc_tags if not (x in seen_neg or seen_neg.add(x))]
                    job['neg_description_tags'] = ", ".join(unique_neg_tags)
                except Exception as e:
                    print(f"Deep scrape error for {job['link']}: {e}")
                    job['description'] = job.get('preview_text', 'Failed to extract content.')
                    
                    # Extract tags from the preview text fallback
                    desc_tags = []
                    for kw in KEYWORDS:
                        if re.search(re.escape(kw), job['description'], re.IGNORECASE):
                            desc_tags.append(kw)
                    seen = set()
                    unique_tags = [x for x in desc_tags if not (x in seen or seen.add(x))]
                    job['description_tags'] = ", ".join(unique_tags)
                    
                    neg_desc_tags = []
                    for nkw in NEGATIVE_KEYWORDS:
                        if re.search(re.escape(nkw), job['description'], re.IGNORECASE):
                            neg_desc_tags.append(nkw)
                    seen_neg = set()
                    unique_neg_tags = [x for x in neg_desc_tags if not (x in seen_neg or seen_neg.add(x))]
                    job['neg_description_tags'] = ", ".join(unique_neg_tags)
                    
                # Remove parser-only fields before DB insertion.
                internal_keys = [
                    key for key in job if key == 'preview_text' or key.startswith('_')
                ]
                for internal_key in internal_keys:
                    del job[internal_key]
                    
                # Final keyword_score: title score (set by make_job) + desc hits - neg desc hits
                desc_hit_count = len([t for t in job.get('description_tags', '').split(',') if t.strip()])
                neg_desc_hit_count = len([t for t in job.get('neg_description_tags', '').split(',') if t.strip()])
                job['keyword_score'] = job.get('keyword_score', 0) + desc_hit_count - neg_desc_hit_count

                # Insert into DB
                database.insert_job(job)
                emit_log(f"  -> UI_RELOAD", log_queue)
                
                # Slight delay between deep scrapes to avoid getting blocked
                page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
                
            if total_jobs > 0:
                emit_log(f"📄 [{domain_name}] P.{page_num}: {total_jobs} found, {new_jobs} new saved", log_queue)
                
            # Slight delay between domain pages
            page.wait_for_timeout(random.randint(DELAY_MIN_MS, DELAY_MAX_MS))
            
            if current_state == STATE_STOPPED:
                break
                
        browser.close()
        
    emit_log("🏁 Scraper finished", log_queue)
        
    if log_queue is not None:
        log_queue.put("DONE")

if __name__ == "__main__":
    main()
