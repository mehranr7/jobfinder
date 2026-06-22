from dataclasses import dataclass

@dataclass
class JobOffer:
    title: str
    date: str
    link: str
    keyword: str
    description: str = ""
    
    def to_dict(self):
        return {
            "title": self.title,
            "date": self.date,
            "link": self.link,
            "keyword": self.keyword,
            "description": self.description
        }
