import sqlite3
import os
import shutil

BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

ROOT_DB = os.path.join(BASE_DIR, "jobs.db")
DATA_DB = os.path.join(DATA_DIR, "jobs.db")

# Auto-migrate root jobs.db to data/jobs.db if data/jobs.db is missing or empty
if os.path.isfile(ROOT_DB) and (not os.path.isfile(DATA_DB) or os.path.getsize(DATA_DB) == 0):
    try:
        shutil.copy2(ROOT_DB, DATA_DB)
        print("✅ Automatically migrated existing jobs.db to data/jobs.db")
    except Exception as e:
        print(f"[!] Migration warning: {e}")

DB_PATH = DATA_DB if os.path.isfile(DATA_DB) else (ROOT_DB if os.path.isfile(ROOT_DB) else DATA_DB)

def get_connection():
    # Detect if we are in a multithreaded context (like Flask)
    # check_same_thread=False is needed for Flask since it might use multiple threads
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            link TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            platform TEXT,
            date_of_release TEXT,
            keywords TEXT,
            negative_keywords TEXT,
            description TEXT,
            description_tags TEXT,
            neg_description_tags TEXT,
            is_done BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'Unseen',
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute('ALTER TABLE jobs ADD COLUMN description_tags TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        c.execute('ALTER TABLE jobs ADD COLUMN neg_description_tags TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT "Unseen"')
        # Run one-time migration for existing data
        c.execute("UPDATE jobs SET status = 'Applied' WHERE is_done = 1 AND status = 'Unseen'")
        c.execute("UPDATE jobs SET status = 'Unseen' WHERE is_done = 0 AND status = 'Unseen'")
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN cv_type TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN app_state TEXT DEFAULT "None"')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN platform TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN note TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN eval_score INTEGER DEFAULT NULL')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        c.execute('ALTER TABLE jobs ADD COLUMN eval_reason TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN selected_cv TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists
        
    try:
        c.execute('ALTER TABLE jobs ADD COLUMN cover_letter TEXT DEFAULT ""')
    except sqlite3.OperationalError:
        pass # Column already exists

    try:
        c.execute('ALTER TABLE jobs ADD COLUMN keyword_score INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass # Column already exists

    conn.commit()
    conn.close()

def job_exists(link):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM jobs WHERE link = ?', (link,))
    result = c.fetchone()
    conn.close()
    return result is not None

def get_existing_job_by_title_and_company(title, company):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT platform, link FROM jobs WHERE LOWER(title) = LOWER(?) AND LOWER(company) = LOWER(?) LIMIT 1', (title, company))
    result = c.fetchone()
    conn.close()
    return dict(result) if result else None

def insert_job(job_dict):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO jobs (link, title, company, platform, date_of_release, keywords, negative_keywords, description, description_tags, neg_description_tags, status, cv_type, app_state, note, keyword_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_dict.get('link'),
            job_dict.get('title'),
            job_dict.get('company', 'Unknown'),
            job_dict.get('platform', ''),
            job_dict.get('date', 'Unknown'),
            job_dict.get('keyword', ''),
            job_dict.get('negative_keyword', ''),
            job_dict.get('description', ''),
            job_dict.get('description_tags', ''),
            job_dict.get('neg_description_tags', ''),
            'Unseen',
            '',
            'None',
            '',
            job_dict.get('keyword_score', 0)
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists
    finally:
        conn.close()

def get_all_jobs():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM jobs ORDER BY discovered_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_jobs_filtered(search="", status="", platforms=None, keywords=None,
                      neg_keywords=None, desc_tags=None, sort="date-desc",
                      page=1, page_size=20, min_score=None, has_score=None):
    """
    Server-side filtering and pagination. All filtering happens in SQLite.
    Returns (jobs: list[dict], total: int).
    """
    conn = get_connection()
    c = conn.cursor()

    conditions = []
    params = []

    if search:
        conditions.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(keywords) LIKE ? OR LOWER(description_tags) LIKE ?)")
        s = f"%{search.lower()}%"
        params.extend([s, s, s, s])

    if status:
        conditions.append("status = ?")
        params.append(status)

    if platforms:
        placeholders = ",".join("?" * len(platforms))
        conditions.append(f"LOWER(platform) IN ({placeholders})")
        params.extend([p.lower() for p in platforms])

    if keywords:
        kw_conds = []
        for kw in keywords:
            kw_conds.append("(LOWER(keywords) LIKE ? OR LOWER(description_tags) LIKE ?)")
            s = f"%{kw.lower()}%"
            params.extend([s, s])
        conditions.append(f"({' OR '.join(kw_conds)})")

    if neg_keywords:
        nkw_conds = []
        for nkw in neg_keywords:
            nkw_conds.append("(LOWER(negative_keywords) LIKE ? OR LOWER(neg_description_tags) LIKE ?)")
            s = f"%{nkw.lower()}%"
            params.extend([s, s])
        conditions.append(f"({' OR '.join(nkw_conds)})")

    if desc_tags:
        dt_conds = []
        for dt in desc_tags:
            dt_conds.append("LOWER(description_tags) LIKE ?")
            params.append(f"%{dt.lower()}%")
        conditions.append(f"({' OR '.join(dt_conds)})")

    if min_score is not None:
        conditions.append("eval_score >= ?")
        params.append(min_score)

    if has_score is True:
        conditions.append("eval_score IS NOT NULL")
    elif has_score is False:
        conditions.append("eval_score IS NULL")

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sort_map = {
        "date-desc":     "discovered_at DESC",
        "date-asc":      "discovered_at ASC",
        "title-asc":     "LOWER(title) ASC",
        "title-desc":    "LOWER(title) DESC",
        "score-desc":    "COALESCE(eval_score, -1) DESC, discovered_at DESC",
        "score-asc":     "CASE WHEN eval_score IS NULL THEN 1 ELSE 0 END, eval_score ASC, discovered_at DESC",
        "kw-score-desc": "COALESCE(keyword_score, 0) DESC, discovered_at DESC",
        "kw-score-asc":  "COALESCE(keyword_score, 0) ASC, discovered_at DESC",
    }
    order_by = sort_map.get(sort, "discovered_at DESC")

    # Total count
    count_sql = f"SELECT COUNT(*) FROM jobs {where_clause}"
    c.execute(count_sql, params)
    total = c.fetchone()[0]

    # Paginated data
    offset = (page - 1) * page_size
    data_sql = f"SELECT * FROM jobs {where_clause} ORDER BY {order_by} LIMIT ? OFFSET ?"
    c.execute(data_sql, params + [page_size, offset])
    rows = c.fetchall()
    conn.close()

    return [dict(row) for row in rows], total


def get_filter_options():
    """
    Returns all distinct values needed to populate filter dropdowns.
    Called once on page load.
    """
    conn = get_connection()
    c = conn.cursor()

    # Distinct platforms
    c.execute("SELECT DISTINCT platform FROM jobs WHERE platform IS NOT NULL AND platform != '' ORDER BY platform")
    platforms = [row[0] for row in c.fetchall()]

    # All keywords (comma-separated field — collect and split)
    c.execute("SELECT keywords, description_tags FROM jobs WHERE keywords IS NOT NULL OR description_tags IS NOT NULL")
    kw_set = set()
    for row in c.fetchall():
        for field in [row[0] or "", row[1] or ""]:
            for kw in field.split(","):
                kw = kw.strip()
                if kw:
                    kw_set.add(kw)

    # All negative keywords
    c.execute("SELECT negative_keywords, neg_description_tags FROM jobs")
    neg_kw_set = set()
    for row in c.fetchall():
        for field in [row[0] or "", row[1] or ""]:
            for kw in field.split(","):
                kw = kw.strip()
                if kw:
                    neg_kw_set.add(kw)

    # Status counts
    c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
    status_counts = {row[0]: row[1] for row in c.fetchall()}

    conn.close()
    return {
        "platforms": platforms,
        "keywords": sorted(kw_set, key=str.lower),
        "neg_keywords": sorted(neg_kw_set, key=str.lower),
        "status_counts": status_counts,
    }

def update_job_status(link, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET status = ? WHERE link = ?', (status, link))
    conn.commit()
    conn.close()

def update_job_cv_type(link, cv_type):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET cv_type = ? WHERE link = ?', (cv_type, link))
    conn.commit()
    conn.close()

def update_job_app_state(link, app_state):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET app_state = ? WHERE link = ?', (app_state, link))
    conn.commit()
    conn.close()

def update_job_note(link, note):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET note = ? WHERE link = ?', (note, link))
    conn.commit()
    conn.close()

def update_job_eval(link, eval_score, eval_reason, selected_cv="", cover_letter=""):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET eval_score = ?, eval_reason = ?, selected_cv = ?, cover_letter = ? WHERE link = ?', (eval_score, eval_reason, selected_cv, cover_letter, link))
    conn.commit()
    conn.close()

def update_job_tags(link, keywords, neg_keywords, desc_tags, neg_desc_tags, keyword_score=None):
    conn = get_connection()
    c = conn.cursor()
    if keyword_score is not None:
        c.execute('''
            UPDATE jobs 
            SET keywords = ?, negative_keywords = ?, description_tags = ?, neg_description_tags = ?, keyword_score = ?
            WHERE link = ?
        ''', (keywords, neg_keywords, desc_tags, neg_desc_tags, keyword_score, link))
    else:
        c.execute('''
            UPDATE jobs 
            SET keywords = ?, negative_keywords = ?, description_tags = ?, neg_description_tags = ? 
            WHERE link = ?
        ''', (keywords, neg_keywords, desc_tags, neg_desc_tags, link))
    conn.commit()
    conn.close()

def update_keyword_score(link, keyword_score):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET keyword_score = ? WHERE link = ?', (keyword_score, link))
    conn.commit()
    conn.close()

def delete_job(link):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM jobs WHERE link = ?', (link,))
    conn.commit()
    conn.close()

def get_jobs_by_links(links):
    if not links:
        return []
    conn = get_connection()
    c = conn.cursor()
    placeholders = ','.join('?' * len(links))
    # Preserve the original order of the links array!
    # SQLite has no ORDER BY FIELD, so we will sort them in Python
    c.execute(f'SELECT * FROM jobs WHERE link IN ({placeholders})', links)
    rows = c.fetchall()
    conn.close()
    
    # Convert to dicts
    jobs = [dict(r) for r in rows]
    # Sort them according to the input links list to preserve frontend sorting
    job_map = {j['link']: j for j in jobs}
    sorted_jobs = [job_map[l] for l in links if l in job_map]
    return sorted_jobs
