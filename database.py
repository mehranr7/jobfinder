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
            is_done BOOLEAN DEFAULT 0,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
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
            INSERT INTO jobs (link, title, company, date_of_release, keywords, negative_keywords, description, is_done)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_dict.get('link'),
            job_dict.get('title'),
            job_dict.get('company', 'Unknown'),
            job_dict.get('date', 'Unknown'),
            job_dict.get('keyword', ''),
            job_dict.get('negative_keyword', ''),
            job_dict.get('description', ''),
            False
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

def update_job_status(link, is_done):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE jobs SET is_done = ? WHERE link = ?', (is_done, link))
    conn.commit()
    conn.close()
