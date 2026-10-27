
import json
import hashlib
import time
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "data" / "books_cache"

API_URL = "https://openlibrary.org/search.json"
COVERS_URL = "https://covers.openlibrary.org/b/id/"

CACHE_TTL = 24 * 60 * 60  # 24 jam
DEFAULT_LIMIT = 30

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "HBook/1.0 (desktop book catalog application)"
})


# ============================================================
# CACHE
# ============================================================

def get_cache_path(query, limit):
    """Membuat nama file cache berdasarkan pencarian."""
    cache_key = hashlib.md5(
        f"{query.lower().strip()}_{limit}".encode("utf-8")
    ).hexdigest()

    return CACHE_DIR / f"{cache_key}.json"


def load_cache(query, limit):
    """Mengambil hasil pencarian dari cache jika masih berlaku."""
    cache_path = get_cache_path(query, limit)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as file:
            cache_data = json.load(file)

        saved_time = cache_data.get("saved_at", 0)

        if time.time() - saved_time <= CACHE_TTL:
            return cache_data.get("books", [])

    except (OSError, json.JSONDecodeError):
        return None

    return None


def save_cache(query, limit, books):
    """Menyimpan hasil pencarian yang berhasil."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        cache_data = {
            "saved_at": time.time(),
            "books": books
        }

        with open(
            get_cache_path(query, limit),
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                cache_data,
                file,
                ensure_ascii=False,
                indent=2
            )

    except (OSError, TypeError) as error:
        print(f"[Open Library] Cache gagal disimpan: {error}")


# ============================================================
# DATA CONVERSION
# ============================================================

def convert_book(item):
    """Mengubah data Open Library ke format yang digunakan HBook."""

    title = item.get("title") or "Judul tidak diketahui"

    authors = item.get("author_name") or []
    authors_text = ", ".join(authors) if authors else "Penulis tidak diketahui"

    subjects = item.get("subject") or []
    categories = ", ".join(subjects[:5]) if subjects else "Tidak diketahui"

    year = item.get("first_publish_year")
    published_date = str(year) if year else ""

    cover_id = item.get("cover_i")
    thumbnail = (
        f"{COVERS_URL}{cover_id}-M.jpg"
        if cover_id
        else ""
    )

    rating = item.get("ratings_average")
    rating_text = f"{rating:.1f}/5" if isinstance(
        rating, (int, float)
    ) else "Belum ada rating"

    work_key = item.get("key", "")
    fullbook = (
        f"https://openlibrary.org{work_key}"
        if work_key.startswith("/works/")
        else ""
    )

    languages = item.get("language") or []
    language = ", ".join(languages[:3]) if languages else "Tidak diketahui"

    return {
        "id": work_key,
        "title": title,
        "authors": authors_text,
        "categories": categories,
        "rating": rating_text,
        "description": "",
        "thumbnail": thumbnail,
        "publishedDate": published_date,
        "fullbook": fullbook,
        "language": language
    }


# ============================================================
# SEARCH BOOKS
# ============================================================

def search_books(query, max_results=DEFAULT_LIMIT):
    """
    Mencari buku melalui Open Library API.

    Format hasil dipertahankan agar kompatibel dengan HBook.
    Jika API gagal, gunakan cache terakhir untuk pencarian tersebut.
    """

    query = (query or "").strip()

    if not query:
        query = "subject:fiction"

    try:
        limit = max(1, min(int(max_results), 100))
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    # Periksa cache terlebih dahulu.
    cached_books = load_cache(query, limit)

    if cached_books is not None:
        print(f"[Open Library] Menggunakan cache: {len(cached_books)} buku")
        return cached_books

    params = {
        "q": query,
        "limit": limit,
        "fields": (
            "key,title,author_name,first_publish_year,"
            "cover_i,subject,ratings_average,language"
        )
    }

    try:
        response = SESSION.get(
            API_URL,
            params=params,
            timeout=(5, 20)
        )
        response.raise_for_status()

        data = response.json()
        documents = data.get("docs", [])

        books = [
            convert_book(item)
            for item in documents
            if item.get("title")
        ]

        save_cache(query, limit, books)

        print(f"[Open Library] Berhasil: {len(books)} buku")
        return books

    except requests.RequestException as error:
        print(f"[Open Library] Permintaan gagal: {error}")

    except (ValueError, TypeError) as error:
        print(f"[Open Library] Respons tidak valid: {error}")

    # Jika cache kedaluwarsa atau API gagal, gunakan cache lama.
    cache_path = get_cache_path(query, limit)

    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as file:
                old_cache = json.load(file)

            books = old_cache.get("books", [])
            print(f"[Open Library] Menggunakan cache lama: {len(books)} buku")
            return books

        except (OSError, json.JSONDecodeError):
            pass

    return []
