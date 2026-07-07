import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")

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

    conn.commit()
    conn.close()

def job_exists(link):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM jobs WHERE link = ?', (link,))
    result = c.fetchone()
    conn.close()
    return result is not None

def insert_job(job_dict):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO jobs (link, title, company, date_of_release, keywords, negative_keywords, description, description_tags, neg_description_tags, status, cv_type, app_state, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_dict.get('link'),
            job_dict.get('title'),
            job_dict.get('company', 'Unknown'),
            job_dict.get('date', 'Unknown'),
            job_dict.get('keyword', ''),
            job_dict.get('negative_keyword', ''),
            job_dict.get('description', ''),
            job_dict.get('description_tags', ''),
            job_dict.get('neg_description_tags', ''),
            'Unseen',
            '',
            'None',
            ''
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
    # Convert sqlite3.Row objects to dicts
    return [dict(row) for row in rows]

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

def delete_job(link):
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM jobs WHERE link = ?', (link,))
    conn.commit()
    conn.close()
