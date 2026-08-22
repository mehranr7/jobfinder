import re
import os
import yaml
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def load_config():
    """
    Safely loads configuration from config.yml.
    Falls back to config.example.yml or an empty dictionary if config.yml is missing or invalid.
    """
    base_dir = os.path.dirname(__file__)
    config_path = os.path.join(base_dir, "config.yml")
    example_path = os.path.join(base_dir, "config.example.yml")
    
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[!] Warning: Error reading {config_path}: {e}")
            
    if os.path.isfile(example_path):
        try:
            with open(example_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
            
    return {}

def truncate(s, length=60):
    return s if len(s) <= length else s[:length-3] + "..."

_REGEX_CACHE = {}

def compile_keyword_regex(term: str) -> re.Pattern:
    """
    Compiles a keyword into a token/word-boundary aware regex pattern.
    Handles alphanumeric words and special symbols like C#, C++, .NET, React.js.
    """
    term = term.strip()
    if not term:
        return None
    escaped = re.escape(term)
    
    # Left boundary: require \b if first char is word char, otherwise require start or non-word char
    if re.match(r'^\w', term, re.UNICODE):
        left = r'\b'
    else:
        left = r'(?:^|(?<=[^\w]))'
        
    # Right boundary: require \b if last char is word char, otherwise require end or non-word char
    if re.match(r'.*\w$', term, re.UNICODE):
        right = r'\b'
    else:
        right = r'(?:$|(?=[^\w]))'
        
    return re.compile(f"{left}{escaped}{right}", re.IGNORECASE | re.UNICODE)

def get_keyword_regex(term: str):
    term_clean = term.strip()
    if not term_clean:
        return None
    if term_clean not in _REGEX_CACHE:
        _REGEX_CACHE[term_clean] = compile_keyword_regex(term_clean)
    return _REGEX_CACHE[term_clean]

def match_keywords(text: str, keywords: list[str]) -> list[str]:
    """
    Finds matching keywords in text using word-boundary matching.
    Returns a deduplicated list of matched keywords in order of appearance in keywords list.
    """
    if not text or not keywords:
        return []
    
    matched = []
    seen_lower = set()
    
    for kw in keywords:
        kw_clean = kw.strip()
        if not kw_clean:
            continue
        kw_lower = kw_clean.lower()
        if kw_lower in seen_lower:
            continue
            
        pattern = get_keyword_regex(kw_clean)
        if pattern and pattern.search(text):
            matched.append(kw_clean)
            seen_lower.add(kw_lower)
            
    return matched

def clean_text(html_content):
    """
    Cleans raw HTML content by removing scripts, styles, navigation, headers, footers,
    cookie banners, and non-content markup. Returns visible text cleanly formatted.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove standard non-content tags
    for tag in soup(["script", "style", "header", "footer", "nav", "noscript", "svg", "img", "aside", "form", "iframe"]):
        tag.extract()
        
    # Remove common cookie/consent/navigation banners by class/id/role attributes
    for el in soup.find_all(attrs={"role": re.compile(r"^(navigation|banner|contentinfo|dialog)$", re.I)}):
        el.extract()
    for el in soup.find_all(class_=re.compile(r"(cookie|consent|banner|header-nav|footer-nav|menu-container|navigation)", re.I)):
        el.extract()
    for el in soup.find_all(id=re.compile(r"(cookie|consent|banner|header|footer|nav)", re.I)):
        el.extract()
        
    # If a <main> or <article> tag exists, prefer extracting from that primary content area
    main_content = soup.find(['main', 'article'])
    target = main_content if main_content and len(main_content.get_text(strip=True)) > 150 else soup

    text = target.get_text(separator='\n', strip=True)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()

def parse_relative_date(date_text):
    """
    Parses English or German relative date strings into an absolute ISO8601 string.
    Returns the original string if parsing fails.
    """
    if not date_text:
        return datetime.now().isoformat(timespec='seconds')
        
    date_text = date_text.lower().strip()
    now = datetime.now()
    
    if 'heute' in date_text or 'today' in date_text or 'gerade' in date_text or 'just now' in date_text:
        return now.isoformat(timespec='seconds')
    if 'gestern' in date_text or 'yesterday' in date_text:
        return (now - timedelta(days=1)).isoformat(timespec='seconds')
        
    match = re.search(r'(\d+)\s*([a-zA-Zäöüß]+)', date_text)
    if match:
        num = int(match.group(1))
        unit = match.group(2)
        
        if 'minut' in unit or unit in ('m', 'min'):
            return (now - timedelta(minutes=num)).isoformat(timespec='seconds')
        elif 'stund' in unit or 'hour' in unit or unit in ('h', 'hr', 'hrs'):
            return (now - timedelta(hours=num)).isoformat(timespec='seconds')
        elif 'tag' in unit or 'day' in unit or unit in ('d',):
            return (now - timedelta(days=num)).isoformat(timespec='seconds')
        elif 'woch' in unit or 'week' in unit or unit in ('w', 'wk', 'wks'):
            return (now - timedelta(weeks=num)).isoformat(timespec='seconds')
        elif 'monat' in unit or 'month' in unit or unit in ('mo', 'mos'):
            return (now - timedelta(days=num*30)).isoformat(timespec='seconds')
            
    return date_text

def timeago_filter(dt_string):
    if not dt_string:
        return "Unknown"
        
    try:
        dt = datetime.fromisoformat(dt_string)
    except ValueError:
        return dt_string
        
    now = datetime.now()
    diff = now - dt
    
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
        
    days = hours // 24
    if days < 7:
        if days == 1:
            return "Yesterday"
        return f"{days} day{'s' if days != 1 else ''} ago"
        
    weeks = days // 7
    if days < 30:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        
    months = max(1, days // 30)
    return f"{months} month{'s' if months != 1 else ''} ago"
