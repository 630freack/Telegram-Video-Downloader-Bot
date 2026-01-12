import sqlite3
from datetime import datetime
import os

def init_db(db_path: str):
    """Initialize the database for storing download history."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_download(url: str, filename: str, filepath: str, timestamp: datetime, db_path: str = 'Z:/proj/neznay/data/history.db'):
    """Save download record to the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO downloads (url, filename, filepath, timestamp) VALUES (?, ?, ?, ?)",
        (url, filename, filepath, timestamp.strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_history(db_path: str = 'Z:/proj/neznay/data/history.db'):
    """Retrieve download history from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT url, filename, filepath, timestamp FROM downloads ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows