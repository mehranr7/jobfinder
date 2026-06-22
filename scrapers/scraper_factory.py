from scrapers.stellenwerk_scraper import StellenwerkScraper
from scrapers.indeed_scraper import IndeedScraper
from scrapers.stepstone_scraper import StepstoneScraper
from scrapers.generic_scraper import GenericScraper

class ScraperFactory:
    def __init__(self, config):
        self.config = config
        self.scrapers = {
            "stellenwerk": StellenwerkScraper(config.keywords, config.delay_min_ms, config.delay_max_ms),
            "indeed": IndeedScraper(config.keywords, config.delay_min_ms, config.delay_max_ms),
            "stepstone": StepstoneScraper(config.keywords, config.delay_min_ms, config.delay_max_ms)
        }
        self.generic_scraper = GenericScraper(
            config.keywords, 
            config.delay_min_ms, 
            config.delay_max_ms, 
            config.job_link_keywords
        )

    def get_scraper(self, url):
        for key, scraper in self.scrapers.items():
            if key in url:
                return key.capitalize(), scraper
        # Fallback to generic scraper for company URLs
        domain = url.split("//")[-1].split("/")[0]
        return domain, self.generic_scraper
