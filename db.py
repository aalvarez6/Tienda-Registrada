import sqlite3
from datetime import datetime
from pathlib import Path

# Inicialización y operaciones de BD
DB_PATH = Path("incidents.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        file_type TEXT,
        timestamp TEXT,
        status TEXT,
        diagnosis TEXT,
        recommendation TEXT,
        hash TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER,
        timestamp TEXT,
        level TEXT,
        message TEXT
    )''')
    conn.commit()
    conn.close()

def save_incident(filename, file_type, status, diagnosis, recommendation, file_hash):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO incidents (filename, file_type, timestamp, status, diagnosis, recommendation, hash)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (filename, file_type, datetime.now().isoformat(), status, diagnosis, recommendation, file_hash))
    incident_id = c.lastrowid
    conn.commit()
    conn.close()
    return incident_id

def save_log(incident_id, level, message):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO logs (incident_id, timestamp, level, message)
                 VALUES (?, ?, ?, ?)''',
              (incident_id, datetime.now().isoformat(), level, message))
    conn.commit()
    conn.close()

def get_all_incidents():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, filename, file_type, timestamp, status, diagnosis, recommendation FROM incidents ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return rows
