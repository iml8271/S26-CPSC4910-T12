import sqlite3

conn = sqlite3.connect('pointfleetdb.db')
cursor = conn.cursor()
cursor.execute("PRAGMA foreign_keys = ON")

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    sponsor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sponsor_name TEXT NOT NULL,
    contact_email TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS drivers (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    driver_fname TEXT NOT NULL,
    driver_lname TEXT NOT NULL,
    driver_points INTEGER DEFAULT 0,
    sponsor_id INTEGER,
    FOREIGN KEY (sponsor_id) REFERENCES sponsors(sponsor_id) ON DELETE SET NULL
)
''')

conn.commit()
conn.close()
print("Database created successfully!")