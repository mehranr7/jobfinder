import sys
from playwright.sync_api import sync_playwright
from config_manager import ConfigManager
from report_generator import ReportGenerator
from scrapers.scraper_factory import ScraperFactory

sys.stdout.reconfigure(encoding='utf-8')

def main():
    config = ConfigManager()
    report_gen = ReportGenerator()
    factory = ScraperFactory(config)
    
    matched_jobs = []
    
    # Combine job board URLs and company URLs
    all_urls = sorted(config.target_urls) + sorted(config.company_urls)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            locale="de-DE"
        )
        
        current_domain = ""
        
        for url in all_urls:
            domain_name, scraper = factory.get_scraper(url)
            
            if domain_name != current_domain:
                print(f"\n[ {domain_name} ]")
                current_domain = domain_name

            jobs = scraper.scrape(page, url)
            
            for job in jobs:
                title_disp = scraper.truncate(job['title'], 50)
                print(f"  -> Match: {job['date']:>12} | {job['keyword']:<15} | {title_disp}")
                
                # Perform deep scrape using the specific scraper
                job = scraper.perform_deep_scrape(page, job)
                
                matched_jobs.append(job)
                
                # Live update the report on each item
                report_gen.generate(matched_jobs, quiet=True)
                
        browser.close()
        
    report_gen.generate(matched_jobs, quiet=False)

if __name__ == "__main__":
    main()
