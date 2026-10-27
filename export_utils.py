
import csv
from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "export"


def ensure_export_dir():
    """Membuat folder export jika belum tersedia."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def get_book_fields(row):
    """
    Membaca format baris database:
    (id, title, authors, category, rating, notes)
    """
    title = row[1] or ""
    authors = row[2] or ""
    category = row[3] or ""
    rating = row[4] or ""
    notes = row[5] or ""

    thumbnail = ""
    published_date = ""
    user_notes = notes

    if "|" in notes:
        parts = notes.split("|", 1)
        thumbnail = parts[0].strip()
        published_date = parts[1].strip()
        user_notes = ""

    return {
        "title": title,
        "authors": authors,
        "category": category,
        "rating": rating,
        "notes": user_notes,
        "thumbnail": thumbnail,
        "published_date": published_date,
    }


def export_to_csv(filename, data):
    """Mengekspor daftar favorit ke CSV dengan encoding UTF-8."""
    if not data:
        return False

    ensure_export_dir()

    path = Path(filename)
    if not path.is_absolute():
        path = EXPORT_DIR / path.name

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)

        writer.writerow([
            "Title",
            "Authors",
            "Category",
            "Rating",
            "Published Date",
            "Notes",
            "Thumbnail URL",
        ])

        for row in data:
            book = get_book_fields(row)

            writer.writerow([
                book["title"],
                book["authors"],
                book["category"],
                book["rating"],
                book["published_date"],
                book["notes"],
                book["thumbnail"],
            ])

    return str(path)


def export_to_pdf(filename, data):
    """Membuat laporan PDF buku favorit dengan format sederhana."""
    if not data:
        return False

    ensure_export_dir()

    path = Path(filename)
    if not path.is_absolute():
        path = EXPORT_DIR / path.name

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Font bawaan FPDF untuk kompatibilitas lintas lingkungan.
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, "Favorite Books Report", ln=True, align="C")

    pdf.set_font("Arial", size=10)
    pdf.cell(
        0,
        7,
        f"Total books: {len(data)}",
        ln=True,
        align="C"
    )
    pdf.ln(8)

    for index, row in enumerate(data, start=1):
        book = get_book_fields(row)

        pdf.set_font("Arial", "B", 12)
        pdf.multi_cell(
            0,
            7,
            f"{index}. {safe_pdf_text(book['title'])}"
        )

        pdf.set_font("Arial", size=10)

        details = [
            ("Author", book["authors"]),
            ("Category", book["category"]),
            ("Rating", book["rating"]),
            ("Published", book["published_date"]),
        ]

        for label, value in details:
            pdf.multi_cell(
                0,
                6,
                f"{label}: {safe_pdf_text(value or '-')}"
            )

        if book["notes"]:
            pdf.multi_cell(
                0,
                6,
                f"Notes: {safe_pdf_text(book['notes'])}"
            )

        pdf.ln(5)

    pdf.output(str(path))
    return str(path)


def safe_pdf_text(value):
    """
    Menghindari error encoding pada font bawaan FPDF.
    Karakter yang tidak didukung akan diganti.
    """
    text = str(value or "")

    try:
        return text.encode("latin-1", errors="replace").decode("latin-1")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
