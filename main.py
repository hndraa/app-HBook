
import sys
from matplotlib.pyplot import title
import requests

from pathlib import Path
from urllib.parse import quote

from PyQt5.QtCore import (
    Qt, QSize, QUrl, QThread, pyqtSignal
)
from PyQt5.QtGui import (
    QFont, QPixmap, QIcon, QPainter,
    QPainterPath, QColor, QDesktopServices
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QFrame,
    QScrollArea, QStackedWidget, QMessageBox,
    QComboBox, QMenuBar, QAction, QSizePolicy,
    QProgressBar
)
from torch import layout

from api_openlibrary import search_books
from database import (
    init_db,
    add_favorite_book,
    get_all_favorite_books,
    remove_favorite_book
)
from export_utils import export_to_pdf, export_to_csv
from PyQt5.QtCore import QRunnable, QThreadPool, QObject, pyqtSignal
from PyQt5.QtGui import QImage


# ============================================================
# PATHS AND THEME
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ASSET_DIR = BASE_DIR / "Asset"

COLORS = {
    "background": "#F7F3FA",
    "surface": "#FFFFFF",
    "surface_soft": "#F0E8F7",
    "primary": "#9B7BB5",
    "primary_dark": "#78578F",
    "primary_light": "#E6D9F0",
    "accent": "#D9B8E4",
    "text": "#392E43",
    "muted": "#82758C",
    "border": "#E7DDEC",
    "success": "#628A70",
    "danger": "#C46F78",
    "white": "#FFFFFF",
}


def asset_path(filename):
    """Mengambil path aset dari folder Asset."""
    return str(ASSET_DIR / filename)


def load_icon(filename):
    """Mengembalikan ikon jika file tersedia."""
    path = Path(asset_path(filename))

    if path.is_file():
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon

    print(f"[Asset] Ikon tidak ditemukan: {path}")
    return QIcon()


def rounded_pixmap(pixmap, radius=10):
    """Membuat gambar dengan sudut membulat."""
    if pixmap.isNull():
        return pixmap

    result = QPixmap(pixmap.size())
    result.fill(Qt.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)

    path = QPainterPath()
    path.addRoundedRect(
        0, 0,
        pixmap.width(), pixmap.height(),
        radius, radius
    )

    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()

    return result


def get_cover_pixmap(url, width=110, height=155):
    """
    Memuat cover dari URL.
    """
    pixmap = QPixmap()

    if url:
        try:
            response = requests.get(
                url.replace("http://", "https://", 1),
                timeout=(3, 5),
                headers={"User-Agent": "HBook/1.0"}
            )
            response.raise_for_status()
            pixmap.loadFromData(response.content)
        except requests.RequestException as error:
            print(f"[Cover] Gagal memuat gambar: {error}")

    if pixmap.isNull():
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(COLORS["primary_light"]))

        painter = QPainter(pixmap)
        painter.setPen(QColor(COLORS["primary_dark"]))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(
            pixmap.rect(),
            Qt.AlignCenter | Qt.TextWordWrap,
            "HBOOK\nNo Cover"
        )
        painter.end()

    pixmap = pixmap.scaled(
        width, height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
    )

    return rounded_pixmap(pixmap, 9)


# ============================================================
# ASYNC COVER LOADER
# ============================================================

class CoverSignals(QObject):
    loaded = pyqtSignal(bytes)
    finished = pyqtSignal(object)


# Menjaga worker tetap hidup sampai unduhan selesai.
ACTIVE_COVER_WORKERS = []


def cleanup_cover_worker(worker):
    if worker in ACTIVE_COVER_WORKERS:
        ACTIVE_COVER_WORKERS.remove(worker)


class CoverWorker(QRunnable):
    def __init__(self, url, signals):
        super().__init__()
        self.url = url
        self.signals = signals
        self.setAutoDelete(False)

    def run(self):
        image_data = b""

        try:
            if self.url:
                response = requests.get(
                    self.url.replace("http://", "https://", 1),
                    timeout=(3, 5),
                    headers={"User-Agent": "HBook/1.0"}
                )
                response.raise_for_status()
                image_data = response.content

        except requests.RequestException as error:
            print(f"[Cover] Gagal memuat gambar: {error}")

        finally:
            self.signals.loaded.emit(image_data)
            self.signals.finished.emit(self)


COVER_THREAD_POOL = QThreadPool.globalInstance()
COVER_THREAD_POOL.setMaxThreadCount(4)


def published_year(book):
    """Mengambil tahun terbit dari metadata buku."""
    date = str(book.get("publishedDate", "") or "")
    return date[:4] if len(date) >= 4 and date[:4].isdigit() else "-"


def book_key(book):
    """Kunci untuk mencocokkan judul dan penulis."""
    return (
        str(book.get("title", "")).strip().casefold(),
        str(book.get("authors", "")).strip().casefold()
    )


def favorite_notes(book):
    thumbnail = book.get("thumbnail", "") or ""
    date = book.get("publishedDate", "") or ""
    return f"{thumbnail}|{date}"


def favorite_to_dict(row):
    """Mengubah baris database favorit menjadi dictionary buku."""
    notes = str(row[5] or "")
    thumbnail = ""
    date = ""

    if "|" in notes:
        thumbnail, date = notes.split("|", 1)

    return {
        "title": row[1] or "",
        "authors": row[2] or "",
        "categories": row[3] or "",
        "rating": row[4] or "N/A",
        "thumbnail": thumbnail,
        "publishedDate": date,
        "description": "Buku yang disimpan dalam daftar favorit.",
        "fullbook": "",
        "language": "",
    }


# ============================================================
# SEARCH WORKER
# ============================================================

class SearchWorker(QThread):

    finished_books = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, query, max_results=30, parent=None):
        super().__init__(parent)
        self.query = query
        self.max_results = max_results

    def run(self):
        try:
            books = search_books(
                self.query,
                max_results=self.max_results
            )
            self.finished_books.emit(books)
        except Exception as error:
            self.failed.emit(str(error))


# ============================================================
# GLOBAL STYLES
# ============================================================

def apply_global_styles(app):
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))

    app.setStyleSheet("""
        QWidget {
            color: #392E43;
            font-family: "Segoe UI", Arial;
            font-size: 9pt;
        }

        QMainWindow {
            background-color: #F7F3FA;
        }

        QWidget#page {
            background-color: #F7F3FA;
        }

        QFrame#card {
            background-color: #FFFFFF;
            border: 1px solid #E7DDEC;
            border-radius: 14px;
        }

        QLabel#brand {
            color: #78578F;
            font-size: 26pt;
            font-weight: 800;
            letter-spacing: 3px;
        }

        QLabel#eyebrow {
            color: #9B7BB5;
            font-size: 8pt;
            font-weight: 700;
            letter-spacing: 2px;
        }

        QLabel#heading {
            color: #392E43;
            font-size: 19pt;
            font-weight: 700;
        }

        QLabel#sectionHeading {
            color: #392E43;
            font-size: 12pt;
            font-weight: 700;
        }

        QLabel#muted {
            color: #82758C;
            font-size: 9pt;
        }

        QLabel#bookTitle {
            color: #392E43;
            font-size: 9pt;
            font-weight: 700;
        }

        QLabel#rating {
            color: #B17B38;
            font-size: 8pt;
            font-weight: 700;
        }

        QLineEdit, QComboBox {
            background-color: #FFFFFF;
            border: 1px solid #E0D4E9;
            border-radius: 9px;
            padding: 9px 11px;
            min-height: 18px;
            selection-background-color: #D9B8E4;
        }

        QLineEdit:focus, QComboBox:focus {
            border: 1px solid #9B7BB5;
            background-color: #FFFEFF;
        }

        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            selection-background-color: #E6D9F0;
            border: 1px solid #E7DDEC;
        }

        QPushButton {
            background-color: #EDE4F4;
            color: #78578F;
            border: 1px solid #E1D3EB;
            border-radius: 9px;
            padding: 8px 13px;
            font-weight: 600;
        }

        QPushButton:hover {
            background-color: #E2D3EF;
        }

        QPushButton:pressed {
            background-color: #D5C2E5;
        }

        QPushButton:disabled {
            background-color: #F1EDF3;
            color: #B6AABD;
            border-color: #E7DDEC;
        }

        QPushButton#primaryButton {
            background-color: #9B7BB5;
            color: #FFFFFF;
            border: none;
        }

        QPushButton#primaryButton:hover {
            background-color: #85649F;
        }

        QPushButton#dangerButton {
            background-color: #F8E9EC;
            color: #B45160;
            border: 1px solid #F0D1D8;
        }

        QPushButton#dangerButton:hover {
            background-color: #F3D9DF;
        }

        QPushButton#iconButton {
            padding: 5px;
            min-width: 30px;
            min-height: 30px;
            border-radius: 15px;
        }

        QScrollArea {
            background-color: transparent;
            border: none;
        }

        QScrollBar:vertical {
            background: #F0E8F7;
            width: 9px;
            margin: 2px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical {
            background: #C9B4D9;
            min-height: 24px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical:hover {
            background: #9B7BB5;
        }

        QScrollBar:horizontal {
            background: #F0E8F7;
            height: 9px;
            margin: 2px;
            border-radius: 4px;
        }

        QScrollBar::handle:horizontal {
            background: #C9B4D9;
            min-width: 24px;
            border-radius: 4px;
        }

        QMenuBar {
            background-color: #F7F3FA;
            color: #78578F;
            padding: 4px;
        }

        QMenuBar::item {
            background: transparent;
            padding: 7px 10px;
            border-radius: 6px;
        }

        QMenuBar::item:selected {
            background-color: #E6D9F0;
        }

        QMenu {
            background-color: #FFFFFF;
            border: 1px solid #E7DDEC;
            padding: 5px;
        }

        QMenu::item {
            padding: 7px 20px;
            border-radius: 5px;
        }

        QMenu::item:selected {
            background-color: #E6D9F0;
        }

        QProgressBar {
            background-color: #EDE4F4;
            border: none;
            border-radius: 4px;
            min-height: 7px;
            max-height: 7px;
            text-align: center;
        }

        QProgressBar::chunk {
            background-color: #9B7BB5;
            border-radius: 4px;
        }

        QMessageBox {
            background-color: #FFFFFF;
        }
    """)


# ============================================================
# BOOK CARD
# ============================================================

class BookCard(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, book, favorite=False, parent=None):
        super().__init__(parent)

        self.book = book
        self.is_favorite = favorite

        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedWidth(135)
        self.setMinimumHeight(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 10)
        layout.setSpacing(8)
        
        cover = QLabel()
        cover.setFixedSize(115, 145)
        cover.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        cover.setContentsMargins(0, 0, 0, 0)
        cover.setStyleSheet("background-color: transparent;")
        cover.setText("Memuat...")

        layout.addWidget(cover, 0, Qt.AlignHCenter)
        self.cover_label = cover

        
        self.cover_signals = CoverSignals()
        self.cover_signals.loaded.connect(self.on_cover_loaded)

        thumbnail_url = book.get("thumbnail", "")

        if thumbnail_url:
            worker = CoverWorker(
                thumbnail_url,
                self.cover_signals
            )

            worker.signals.finished.connect(cleanup_cover_worker)

            # Simpan referensi sebelum worker dijalankan.
            ACTIVE_COVER_WORKERS.append(worker)
            COVER_THREAD_POOL.start(worker)
        else:
            cover.setText("HBOOK\nNo Cover")



        title = QLabel(book.get("title", "Untitled"))
        title.setObjectName("bookTitle")
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignCenter)
        title.setMinimumHeight(38)
        title.setMaximumHeight(45)
        layout.addWidget(title)

        authors = QLabel(book.get("authors", "Unknown author"))
        authors.setObjectName("muted")
        authors.setWordWrap(True)
        authors.setAlignment(Qt.AlignCenter)
        authors.setMaximumHeight(30)
        layout.addWidget(authors)

        bottom = QHBoxLayout()

        rating = book.get("rating", "N/A")
        rating_label = QLabel(f"★ {rating}")
        rating_label.setObjectName("rating")
        bottom.addWidget(rating_label)

        bottom.addStretch()

        year_label = QLabel(published_year(book))
        year_label.setObjectName("muted")
        bottom.addWidget(year_label)

        layout.addLayout(bottom)

        if favorite:
            favorite_label = QLabel("♥ Favorite")
            favorite_label.setAlignment(Qt.AlignCenter)
            favorite_label.setStyleSheet(
                "color: #B66A8A; font-weight: 700;"
            )
            layout.addWidget(favorite_label)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.book)
        super().mousePressEvent(event)

    
    def on_cover_loaded(self, image_data):
        if not image_data:
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("HBOOK\nNo Cover")
            self.cover_label.setAlignment(Qt.AlignCenter)
            return

        image = QImage()

        if not image.loadFromData(image_data):
            self.cover_label.setPixmap(QPixmap())
            self.cover_label.setText("HBOOK\nNo Cover")
            self.cover_label.setAlignment(Qt.AlignCenter)
            return

        pixmap = QPixmap.fromImage(image)

        
        pixmap = pixmap.scaled(
            self.cover_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setPixmap(rounded_pixmap(pixmap, 7))

# ============================================================
# BOOK DETAIL PAGE
# ============================================================

class BookDetailPage(QWidget):
    favorite_changed = pyqtSignal()

    def __init__(self, book, parent=None):
        super().__init__(parent)

        self.book = book
        self.favorite_rows = get_all_favorite_books()
        self.is_favorite = any(
            row[1] == book.get("title", "")
            and (row[2] or "") == (book.get("authors", "") or "")
            for row in self.favorite_rows
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(9)

        top = QHBoxLayout()

        back_button = QPushButton("← Kembali")
        back_button.clicked.connect(self.go_back)
        top.addWidget(back_button)
        top.addStretch()

        root.addLayout(top)

        card = QFrame()
        card.setObjectName("card")

        content = QHBoxLayout(card)
        content.setContentsMargins(22, 22, 22, 22)
        content.setSpacing(22)

        cover = QLabel()
        cover.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        cover.setPixmap(
           get_cover_pixmap(book.get("thumbnail", ""), 130, 185)
        )
        cover.setFixedWidth(140)
        content.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(11)

        eyebrow = QLabel("BOOK DETAILS")
        eyebrow.setObjectName("eyebrow")
        info.addWidget(eyebrow)

        title = QLabel(book.get("title", "Untitled"))
        title.setObjectName("heading")
        title.setWordWrap(True)
        info.addWidget(title)

        info.addWidget(QLabel(
            f"Penulis: {book.get('authors', '-') or '-'}"
        ))
        info.addWidget(QLabel(
            f"Tahun terbit: {published_year(book)}"
        ))
        info.addWidget(QLabel(
            f"Genre: {book.get('categories', '-') or '-'}"
        ))
        info.addWidget(QLabel(
            f"Bahasa: {book.get('language', '-') or '-'}"
        ))
        info.addWidget(QLabel(
            f"Rating: ★ {book.get('rating', 'N/A')}"
        ))

        description_title = QLabel("Deskripsi")
        description_title.setObjectName("sectionHeading")
        info.addWidget(description_title)

        description = QLabel(
            book.get("description", "") or "Deskripsi belum tersedia."
        )
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignTop)
        description.setTextInteractionFlags(Qt.TextSelectableByMouse)

        description_scroll = QScrollArea()
        description_scroll.setWidgetResizable(True)
        description_scroll.setMinimumHeight(100)
        description_scroll.setMaximumHeight(180)

        description_container = QWidget()
        description_layout = QVBoxLayout(description_container)
        description_layout.setContentsMargins(0, 0, 0, 0)
        description_layout.addWidget(description)
        description_scroll.setWidget(description_container)

        info.addWidget(description_scroll)

        actions = QHBoxLayout()

        self.favorite_button = QPushButton()
        self.favorite_button.setObjectName("primaryButton")
        self.update_favorite_button()
        self.favorite_button.clicked.connect(self.toggle_favorite)
        actions.addWidget(self.favorite_button)

        share_button = QPushButton("Bagikan")
        share_button.clicked.connect(self.share_book)
        actions.addWidget(share_button)

        read_button = QPushButton("Lihat Buku")
        read_button.clicked.connect(self.open_book_link)
        actions.addWidget(read_button)

        info.addLayout(actions)
        info.addStretch()

        content.addLayout(info, 1)
        root.addWidget(card, 1)

    def go_back(self):
        window = self.window()
        if hasattr(window, "show_catalog"):
            window.show_catalog()

    def update_favorite_button(self):
        self.favorite_button.setText(
            "♥ Hapus dari Favorit" if self.is_favorite
            else "♡ Simpan ke Favorit"
        )

    def toggle_favorite(self):
        title = self.book.get("title", "")
        authors = self.book.get("authors", "")

        rows = get_all_favorite_books()
        matching = [
            row for row in rows
            if row[1] == title and (row[2] or "") == (authors or "")
        ]

        if matching:
            for row in matching:
                remove_favorite_book(row[0])

            self.is_favorite = False
            QMessageBox.information(
                self, "Favorit", "Buku dihapus dari favorit."
            )
        else:
            notes = favorite_notes(self.book)
            added = add_favorite_book(
                title,
                authors,
                self.book.get("categories", ""),
                str(self.book.get("rating", "")),
                notes
            )

            if added is False:
                QMessageBox.information(
                    self, "Favorit", "Buku sudah tersimpan."
                )
            else:
                QMessageBox.information(
                    self, "Favorit", "Buku berhasil disimpan."
                )

            self.is_favorite = True

        self.update_favorite_button()
        self.favorite_changed.emit()

    def share_book(self):
        title = self.book.get("title", "")
        authors = self.book.get("authors", "")
        url = self.book.get("fullbook", "")

        text = f"{title} — {authors}"
        if url:
            text += f"\n{url}"

        QApplication.clipboard().setText(text)
        QMessageBox.information(
            self, "Bagikan Buku",
            "Informasi buku disalin ke clipboard."
        )

    def open_book_link(self):
        url = self.book.get("fullbook", "")

        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            QMessageBox.information(
                self,
                "Informasi",
                "Tautan buku belum tersedia."
            )


# ============================================================
# WELCOME PAGE
# ============================================================

class WelcomePage(QWidget):
    continue_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("page")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        root.addStretch()

        hero = QFrame()
        hero.setObjectName("card")

        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(34, 24, 34, 28)
        hero_layout.setSpacing(13)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)

        logo_file = Path(asset_path("logo.png"))

        if logo_file.is_file():
            pixmap = QPixmap(str(logo_file))
            if not pixmap.isNull():
                logo.setPixmap(
                pixmap.scaled(
                    140, 140,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )
            logo.setMinimumSize(150, 145)
        else:
            logo.setText("H")
            logo.setStyleSheet(
                "font-size: 44pt; font-weight: 800; color: #9B7BB5;"
            )

        hero_layout.addWidget(logo)

        eyebrow = QLabel("YOUR PERSONAL READING SPACE")
        eyebrow.setObjectName("eyebrow")
        eyebrow.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(eyebrow)

        title = QLabel("Welcome to HBook")
        title.setObjectName("brand")
        title.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(title)

        subtitle = QLabel(
            "Discover books, explore new ideas, and build "
            "your own collection of favorites."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(subtitle)

        start_button = QPushButton("Jelajahi Buku  →")
        start_button.setObjectName("primaryButton")
        start_button.setMinimumWidth(180)
        start_button.clicked.connect(self.continue_clicked.emit)
        hero_layout.addWidget(start_button, alignment=Qt.AlignCenter)

        root.addWidget(hero, alignment=Qt.AlignCenter)
        root.addStretch()

        footer = QLabel("HBOOK  •  FIND YOUR NEXT FAVORITE BOOK")
        footer.setObjectName("muted")
        footer.setAlignment(Qt.AlignCenter)
        root.addWidget(footer)


# ============================================================
# CATALOG PAGE
# ============================================================

class CatalogPage(QWidget):
    favorites_clicked = pyqtSignal()
    detail_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.books = []
        self.filtered_books = []
        self.search_worker = None
        self.active_filter = "Semua"
        self.filter_value = "Semua"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # Header
        header = QHBoxLayout()

        brand_column = QVBoxLayout()
        eyebrow = QLabel("DISCOVER YOUR NEXT READ")
        eyebrow.setObjectName("eyebrow")

        title = QLabel("HBook")
        title.setObjectName("heading")

        brand_column.addWidget(eyebrow)
        brand_column.addWidget(title)

        header.addLayout(brand_column)
        header.addStretch()

        self.favorites_button = QPushButton()
        self.favorites_button.setIcon(load_icon("favorite_on.png"))
        self.favorites_button.setIconSize(QSize(21, 21))
        self.favorites_button.setText(" Favorit")
        self.favorites_button.clicked.connect(self.favorites_clicked.emit)
        header.addWidget(self.favorites_button)

        root.addLayout(header)

        # Search
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Cari judul buku atau nama penulis..."
        )
        self.search_input.returnPressed.connect(self.search_books)
        search_row.addWidget(self.search_input, 1)

        search_button = QPushButton("Cari")
        search_button.setObjectName("primaryButton")
        search_button.clicked.connect(self.search_books)
        search_row.addWidget(search_button)

        root.addLayout(search_row)

        # Filters
        filter_card = QFrame()
        filter_card.setObjectName("card")

        filter_row = QHBoxLayout(filter_card)
        filter_row.setContentsMargins(12, 8, 12, 8)
        filter_row.setSpacing(9)

        filter_label = QLabel("Filter")
        filter_label.setObjectName("sectionHeading")
        filter_row.addWidget(filter_label)

        self.filter_type = QComboBox()
        self.filter_type.addItems([
            "Semua", "Tahun", "Bahasa", "Genre", "Alfabet"
        ])
        self.filter_type.currentTextChanged.connect(
            self.on_filter_type_changed
        )
        filter_row.addWidget(self.filter_type)

        self.filter_value_combo = QComboBox()
        self.filter_value_combo.addItem("Semua")
        self.filter_value_combo.currentTextChanged.connect(
            self.apply_filters
        )
        filter_row.addWidget(self.filter_value_combo, 1)

        reset_filter = QPushButton("Reset")
        reset_filter.clicked.connect(self.reset_filters)
        filter_row.addWidget(reset_filter)

        root.addWidget(filter_card)

        # Status and loading
        status_row = QHBoxLayout()

        self.status_label = QLabel("Cari buku untuk mulai menjelajah.")
        self.status_label.setObjectName("muted")
        status_row.addWidget(self.status_label, 1)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setFixedWidth(90)
        self.loading_bar.hide()
        status_row.addWidget(self.loading_bar)

        root.addLayout(status_row)

        # Results
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.results_container = QWidget()
        self.grid = QGridLayout(self.results_container)
        self.grid.setContentsMargins(5, 5, 5, 5)
        self.grid.setHorizontalSpacing(13)
        self.grid.setVerticalSpacing(13)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.results_container)
        root.addWidget(self.scroll, 1)

   
    def search_books(self):
        # Kata kunci kosong tetap kosong di kolom pencarian.
        # Pencarian rekomendasi menggunakan query internal.
        query = self.search_input.text().strip()

        if not query:
            query = "subject:fiction"

        if self.search_worker and self.search_worker.isRunning():
            self.status_label.setText(
                "Pencarian sebelumnya masih berjalan."
            )
            return

        self.loading_bar.show()
        self.status_label.setText("Sedang mencari buku...")
        self.clear_results()

        self.search_worker = SearchWorker(query, 30, self)
        self.search_worker.finished_books.connect(
            self.on_search_finished
        )
        self.search_worker.failed.connect(
            self.on_search_failed
        )
        self.search_worker.start()


    def on_search_finished(self, books):
        self.loading_bar.hide()
        self.books = books

        if not books:
            self.status_label.setText(
                "Buku tidak ditemukan atau API tidak merespons."
            )
            self.show_empty_state(
                "Belum ada buku yang dapat ditampilkan",
                "Periksa koneksi internet, lalu coba kata kunci lain."
            )
            return

        self.populate_filter_values()
        self.apply_filters()

        self.status_label.setText(
            f"{len(books)} buku berhasil dimuat."
        )

    def on_search_failed(self, error):
        self.loading_bar.hide()
        self.status_label.setText("Pencarian gagal.")
        QMessageBox.warning(
            self,
            "Pencarian Gagal",
            f"Terjadi kesalahan saat mencari buku:\n{error}"
        )

    def clear_results(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def show_empty_state(self, title, description):
        self.clear_results()

        card = QFrame()
        card.setObjectName("card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 30, 24, 30)

        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        heading.setAlignment(Qt.AlignCenter)

        message = QLabel(description)
        message.setObjectName("muted")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)

        layout.addWidget(heading)
        layout.addWidget(message)

        self.grid.addWidget(card, 0, 0)

    def populate_filter_values(self):
        filter_type = self.filter_type.currentText()
        values = set()

        if filter_type == "Tahun":
            values = {
                published_year(book)
                for book in self.books
                if published_year(book) != "-"
            }

        elif filter_type == "Bahasa":
            values = {
                book.get("language", "")
                for book in self.books
                if book.get("language")
            }

        elif filter_type == "Genre":
            for book in self.books:
                categories = book.get("categories", "")
                if categories:
                    values.add(categories.split(",")[0].strip())

        elif filter_type == "Alfabet":
            values = {
                (book.get("title", "").strip()[:1].upper())
                for book in self.books
                if book.get("title", "").strip()
            }

        self.filter_value_combo.blockSignals(True)
        self.filter_value_combo.clear()
        self.filter_value_combo.addItem("Semua")

        for value in sorted(values, reverse=(filter_type == "Tahun")):
            self.filter_value_combo.addItem(value)

        self.filter_value_combo.blockSignals(False)

    def on_filter_type_changed(self, value):
        self.populate_filter_values()
        self.apply_filters()

    def reset_filters(self):
        self.filter_type.setCurrentIndex(0)
        self.filter_value_combo.setCurrentIndex(0)
        self.apply_filters()

    
    def apply_filters(self, *args):
        if not self.books:
            return

        filter_type = self.filter_type.currentText()
        filter_value = self.filter_value_combo.currentText()
        query = self.search_input.text().strip().casefold()

        results = []

        for book in self.books:
            title = str(book.get("title", "") or "")
            authors = str(book.get("authors", "") or "")
            categories = str(book.get("categories", "") or "")
            language = str(book.get("language", "") or "")
            year = published_year(book)

            # Filter berdasarkan kata kunci pencarian.
            if query and (
                query not in title.casefold()
                and query not in authors.casefold()
            ):
                continue

            # Filter berdasarkan nilai yang dipilih.
            if filter_value != "Semua":
                if filter_type == "Tahun" and year != filter_value:
                    continue

                elif filter_type == "Bahasa" and language != filter_value:
                    continue

                elif filter_type == "Genre" and filter_value not in categories:
                    continue

                elif filter_type == "Alfabet":
                    if not title.upper().startswith(filter_value.upper()):
                        continue

            results.append(book)

        # Pengurutan berdasarkan jenis filter aktif.
        if filter_type == "Tahun":
            results.sort(
                key=lambda book: published_year(book),
                reverse=True
            )

        elif filter_type == "Bahasa":
            results.sort(
                key=lambda book: str(book.get("language", "")).casefold()
            )

        elif filter_type == "Genre":
            results.sort(
                key=lambda book: str(book.get("categories", "")).casefold()
            )

        elif filter_type == "Alfabet":
            results.sort(
                key=lambda book: str(book.get("title", "")).casefold()
            )

        self.filtered_books = results
        self.render_books(results)

        self.status_label.setText(
            f"Menampilkan {len(results)} dari {len(self.books)} buku."
        )

    
    def render_books(self, books):
        self.clear_results()

        if not books:
            self.show_empty_state(
                "Tidak ada buku yang cocok",
                "Coba ubah kata kunci atau filter."
            )
            return

        columns = 5

        for index, book in enumerate(books):
            card = BookCard(book)

            card.clicked.connect(self.detail_requested.emit)

            row = index // columns
            column = index % columns

            # Pusatkan kartu di dalam setiap sel grid.
            self.grid.addWidget(
                card,
                row,
                column,
                alignment=Qt.AlignHCenter | Qt.AlignTop
            )

        # Hilangkan stretch kolom yang sebelumnya memengaruhi
        # persebaran ruang kartu.
        for column in range(columns):
            self.grid.setColumnStretch(column, 0)



# ============================================================
# FAVORITES PAGE
# ============================================================

class FavoritesPage(QWidget):
    back_clicked = pyqtSignal()
    detail_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        header = QHBoxLayout()

        back_button = QPushButton("← Kembali ke Katalog")
        back_button.clicked.connect(self.back_clicked.emit)
        header.addWidget(back_button)

        title = QLabel("Buku Favorit")
        title.setObjectName("heading")
        header.addWidget(title)

        header.addStretch()

        root.addLayout(header)

        subtitle = QLabel(
            "Koleksi buku yang kamu simpan untuk dibaca nanti."
        )
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(5, 5, 5, 5)
        self.grid.setHorizontalSpacing(13)
        self.grid.setVerticalSpacing(13)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        actions = QHBoxLayout()

        pdf_button = QPushButton("Ekspor PDF")
        pdf_button.setIcon(load_icon("pdf.png"))
        pdf_button.clicked.connect(self.export_pdf)

        csv_button = QPushButton("Ekspor CSV")
        csv_button.setIcon(load_icon("csv.png"))
        csv_button.clicked.connect(self.export_csv)

        actions.addWidget(pdf_button)
        actions.addWidget(csv_button)
        actions.addStretch()

        root.addLayout(actions)

    def refresh(self):
        self.clear_results()

        rows = get_all_favorite_books()

        if not rows:
            card = QFrame()
            card.setObjectName("card")

            layout = QVBoxLayout(card)
            layout.setContentsMargins(25, 30, 25, 30)

            title = QLabel("Belum ada buku favorit")
            title.setObjectName("sectionHeading")
            title.setAlignment(Qt.AlignCenter)

            message = QLabel(
                "Simpan buku dari halaman detail untuk melihatnya di sini."
            )
            message.setObjectName("muted")
            message.setWordWrap(True)
            message.setAlignment(Qt.AlignCenter)

            layout.addWidget(title)
            layout.addWidget(message)
            self.grid.addWidget(card, 0, 0)
            return

        for index, row in enumerate(rows):
            book = favorite_to_dict(row)

            card = BookCard(book, favorite=True)
            card.clicked.connect(self.detail_requested.emit)

            self.grid.addWidget(card, index // 5, index % 5)

    def clear_results(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def export_pdf(self):
        data = get_all_favorite_books()

        if not data:
            QMessageBox.information(
                self, "Ekspor", "Belum ada buku favorit untuk diekspor."
            )
            return

        try:
            result = export_to_pdf("favorite_books.pdf", data)

            if result:
                QMessageBox.information(
                    self,
                    "Ekspor Berhasil",
                    f"PDF berhasil disimpan di:\n{result}"
                )
        except Exception as error:
            QMessageBox.critical(
                self, "Ekspor Gagal", str(error)
            )

    def export_csv(self):
        data = get_all_favorite_books()

        if not data:
            QMessageBox.information(
                self, "Ekspor", "Belum ada buku favorit untuk diekspor."
            )
            return

        try:
            result = export_to_csv("favorite_books.csv", data)

            if result:
                QMessageBox.information(
                    self,
                    "Ekspor Berhasil",
                    f"CSV berhasil disimpan di:\n{result}"
                )
        except Exception as error:
            QMessageBox.critical(
                self, "Ekspor Gagal", str(error)
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class HBookApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HBook — Book Discovery")
        self.resize(850, 600)
        self.setMinimumSize(700, 500)

        init_db()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.welcome_page = WelcomePage()
        self.catalog_page = CatalogPage()
        self.favorites_page = FavoritesPage()

        self.stack.addWidget(self.welcome_page)
        self.stack.addWidget(self.catalog_page)
        self.stack.addWidget(self.favorites_page)

        self.current_detail_page = None
        self.previous_page = self.catalog_page

        self.create_menu()

        self.welcome_page.continue_clicked.connect(self.show_catalog)
        self.catalog_page.favorites_clicked.connect(self.show_favorites)
        self.catalog_page.detail_requested.connect(self.show_book_detail)
        self.favorites_page.back_clicked.connect(self.show_catalog)
        self.favorites_page.detail_requested.connect(self.show_book_detail)

        self.stack.setCurrentWidget(self.welcome_page)

    def create_menu(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")

        home_action = QAction("Welcome", self)
        home_action.triggered.connect(
            lambda: self.stack.setCurrentWidget(self.welcome_page)
        )
        file_menu.addAction(home_action)

        catalog_action = QAction("Katalog Buku", self)
        catalog_action.triggered.connect(self.show_catalog)
        file_menu.addAction(catalog_action)

        favorites_action = QAction("Buku Favorit", self)
        favorites_action.triggered.connect(self.show_favorites)
        file_menu.addAction(favorites_action)

        file_menu.addSeparator()

        exit_action = QAction("Keluar", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("Bantuan")

        about_action = QAction("Tentang HBook", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    
    def show_catalog(self):
        self.previous_page = self.catalog_page
        self.stack.setCurrentWidget(self.catalog_page)
        self.favorites_page.refresh()

        # Muat rekomendasi otomatis tanpa mengisi kolom pencarian.
        if not self.catalog_page.books and not (
            self.catalog_page.search_worker
            and self.catalog_page.search_worker.isRunning()
        ):
            self.catalog_page.search_books()


    def show_favorites(self):
        self.previous_page = self.favorites_page
        self.favorites_page.refresh()
        self.stack.setCurrentWidget(self.favorites_page)

    def show_book_detail(self, book):
        if self.stack.currentWidget() != self.current_detail_page:
            self.previous_page = self.stack.currentWidget()

        if self.current_detail_page is not None:
            self.stack.removeWidget(self.current_detail_page)
            self.current_detail_page.deleteLater()
            self.current_detail_page = None

        self.current_detail_page = BookDetailPage(book)
        self.current_detail_page.favorite_changed.connect(
            self.favorites_page.refresh
        )

        self.stack.addWidget(self.current_detail_page)
        self.stack.setCurrentWidget(self.current_detail_page)

    def show_about(self):
        QMessageBox.about(
            self,
            "HBook — Book Discovery\n\n"
            "Aplikasi desktop untuk mencari buku melalui Open Library, "
            "melihat detail buku, menyimpan favorit, dan mengekspor "
            "koleksi dalam format PDF atau CSV.\n\n"
            "Built with Python, PyQt5, SQLite, and Open Library API."
        )

    def closeEvent(self, event):
        catalog = getattr(self, "catalog_page", None)

        if catalog is not None:
            worker = catalog.search_worker

            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.quit()
                worker.wait(3000)

        event.accept()


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

def main():
    app = QApplication(sys.argv)
    apply_global_styles(app)

    window = HBookApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
