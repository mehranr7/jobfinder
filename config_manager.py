import yaml

class ConfigManager:
    def __init__(self, config_path="config.yml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        self.target_urls = self.config.get("target_urls") or []
        self.company_urls = self.config.get("company_urls") or []
        self.keywords = self.config.get("keywords") or []
        self.job_link_keywords = self.config.get("job_link_keywords") or []
        self.delay_min_ms = self.config.get("delay_min_ms", 1500)
        self.delay_max_ms = self.config.get("delay_max_ms", 3500)
        
        self.max_depth = self.config.get("max_depth", 2)
        self.navigation_keywords = self.config.get("navigation_keywords") or []
        self.portal_indicator_keywords = self.config.get("portal_indicator_keywords") or []
        self.pagination_keywords = self.config.get("pagination_keywords") or []
