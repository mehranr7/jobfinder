import yaml

class ConfigManager:
    def __init__(self, config_path="config.yml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        self.target_urls = self.config.get("target_urls", [])
        self.company_urls = self.config.get("company_urls", [])
        self.keywords = self.config.get("keywords", [])
        self.job_link_keywords = self.config.get("job_link_keywords", [])
        self.delay_min_ms = self.config.get("delay_min_ms", 1500)
        self.delay_max_ms = self.config.get("delay_max_ms", 3500)
