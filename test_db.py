import sqlite3
conn = sqlite3.connect('jobs.db')
c = conn.cursor()
c.execute("SELECT date_of_release FROM jobs WHERE date_of_release NOT LIKE '2026-%' LIMIT 10")
print(c.fetchall())
conn.close()
