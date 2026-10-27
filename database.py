
import sqlite3
from pathlib import Path

# Gunakan lokasi file, bukan direktori kerja terminal.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "books.db"


def get_connection():
    """Membuka koneksi ke database yang sudah digunakan proyek."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """
    Membuat tabel jika belum ada.
    Tidak menghapus atau mengganti tabel maupun data yang sudah tersimpan.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorite_books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                authors TEXT,
                category TEXT,
                rating TEXT,
                notes TEXT
            )
        """)
        conn.commit()


def add_favorite_book(title, authors, category, rating, notes):
    """Menyimpan buku favorit tanpa mengubah struktur tabel lama."""
    title = (title or "").strip()

    if not title:
        raise ValueError("Judul buku tidak boleh kosong.")

    with get_connection() as conn:
        # Cegah duplikasi berdasarkan judul dan penulis.
        existing = conn.execute(
            """
            SELECT id
            FROM favorite_books
            WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))
              AND LOWER(TRIM(COALESCE(authors, ''))) =
                  LOWER(TRIM(COALESCE(?, '')))
            LIMIT 1
            """,
            (title, authors or "")
        ).fetchone()

        if existing:
            return False

        conn.execute(
            """
            INSERT INTO favorite_books
                (title, authors, category, rating, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                title,
                authors or "",
                category or "",
                str(rating or ""),
                notes or ""
            )
        )
        conn.commit()

    return True


def get_all_favorite_books():
    """Mengembalikan data dengan urutan kolom yang kompatibel."""
    init_db()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, authors, category, rating, notes
            FROM favorite_books
            ORDER BY id DESC
        """).fetchall()

    return rows


def remove_favorite_book(book_id):
    """Menghapus satu buku berdasarkan ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM favorite_books WHERE id = ?",
            (book_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
