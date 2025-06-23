import requests

def search_books(query, max_results=15):
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={max_results}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return []

    books = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        books.append({
            "title": info.get("title", "Judul tidak diketahui"),
            "authors": ", ".join(info.get("authors", ["Penulis tidak diketahui"])),
            "categories": ", ".join(info.get("categories", ["Kategori tidak diketahui"])),
            "rating": info.get("averageRating", "N/A"),
            "description": info.get("description", "")[:200],
            "thumbnail": info.get("imageLinks", {}).get("thumbnail", ""),
            "publishedDate": info.get("publishedDate", ""),
            "language": info.get("language", "")
        })
    return books
