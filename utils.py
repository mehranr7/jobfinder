import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

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
        return "Unbekannt"
        
    try:
        dt = datetime.fromisoformat(dt_string)
    except ValueError:
        return dt_string
        
    now = datetime.now()
    diff = now - dt
    
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Gerade eben"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"vor {minutes} Minute{'n' if minutes != 1 else ''}"
        
    hours = minutes // 60
    if hours < 24:
        return f"vor {hours} Stunde{'n' if hours != 1 else ''}"
        
    days = hours // 24
    if days < 7:
        if days == 1:
            return "Gestern"
        return f"vor {days} Tag{'en' if days != 1 else ''}"
        
    weeks = days // 7
    if weeks < 4:
        return f"vor {weeks} Woche{'n' if weeks != 1 else ''}"
        
    months = days // 30
    return f"vor {months} Monat{'en' if months != 1 else ''}"
