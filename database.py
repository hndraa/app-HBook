import sqlite3
import os

DB_PATH = "data/books.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorite_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            authors TEXT,
            category TEXT,
            rating TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_favorite_book(title, authors, category, rating, notes):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO favorite_books (title, authors, category, rating, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, authors, category, rating, notes))
    conn.commit()
    conn.close()

def get_all_favorite_books():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM favorite_books')
    rows = cursor.fetchall()
    conn.close()
    return rows

def remove_favorite_book(book_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM favorite_books WHERE id=?", (book_id,))
    conn.commit()
    conn.close()