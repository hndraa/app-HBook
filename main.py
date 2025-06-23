import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QStatusBar, QMenuBar, QAction, QMessageBox, QGridLayout, QStackedWidget, QFrame, QSizePolicy
)

from PyQt5.QtGui import QFont, QPixmap, QFontMetrics, QPainter, QPainterPath, QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QSize, QUrl
from api_googlebooks import search_books
from database import init_db, add_favorite_book, get_all_favorite_books, remove_favorite_book
from export_utils import export_to_pdf, export_to_csv

def rounded_pixmap(pixmap, radius):
    size = pixmap.size()
    rounded = QPixmap(size)
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded

class BookWidget(QWidget):
    def __init__(self, book, parent=None):
        super().__init__(parent)
        self.book = book
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        self.setStyleSheet("""
            border-radius: 14px;
            
            background: transparent;
        """)

        # Gambar buku (fixed size, center, rounded corner)
        img_url = book.get("thumbnail", "")
        pixmap = QPixmap()
        if img_url:
            try:
                response = requests.get(img_url)
                pixmap.loadFromData(response.content)
            except Exception:
                pixmap = QPixmap()
        if pixmap.isNull():
            pixmap = QPixmap(100, 140)
            pixmap.fill(Qt.lightGray)
        pixmap = pixmap.scaled(100, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap = rounded_pixmap(pixmap, 12)
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setFixedSize(100, 140)
        img_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(img_label, alignment=Qt.AlignCenter)

        # Judul (maksimal 2 baris, elipsis jika panjang)
        title_label = QLabel()
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        # title_label.setFixedWidth(100)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(36)  # kira-kira 2 baris
        # Potong judul jika terlalu panjang
        fm = QFontMetrics(title_label.font())
        elided_title = fm.elidedText(book["title"], Qt.ElideRight, 100)
        title_label.setText(elided_title)
        title_label.setMaximumHeight(36)
        layout.addWidget(title_label)

        # Baris bawah: penulis kiri, rating kanan
        bottom_layout = QHBoxLayout()
        author_label = QLabel(book["authors"])
        author_label.setFont(QFont("Segoe UI", 5))
        author_label.setStyleSheet("color: #555; background: transparent;")
        author_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # author_label.setFixedWidth(60)
        rating = book.get("rating", "N/A")
        rating_label = QLabel(f"⭐ {rating}")
        rating_label.setFont(QFont("Segoe UI", 8))
        rating_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # rating_label.setFixedWidth(40)
        bottom_layout.addWidget(author_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(rating_label)
        layout.addLayout(bottom_layout)

        self.setLayout(layout)
        self.setFixedWidth(120)
        self.setFixedHeight(210)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Cari parent bertipe BookRecommenderApp
            parent = self.parent()
            while parent is not None and not isinstance(parent, BookRecommenderApp):
                parent = parent.parent()
            if parent and hasattr(parent, "show_book_detail"):
                parent.show_book_detail(self.book)

class BookDetailWidget(QWidget):
    def __init__(self, book, on_close, parent=None):
        super().__init__(parent)
        self.book = book
        self.setFixedWidth(350)
        self.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f3e9f1, stop:1 #e0d7ea);
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # Gambar buku
        img_url = book.get("thumbnail", "")
        pixmap = QPixmap()
        if img_url:
            try:
                response = requests.get(img_url)
                pixmap.loadFromData(response.content)
            except Exception:
                pixmap = QPixmap()
        if pixmap.isNull():
            pixmap = QPixmap(120, 200)
            pixmap.fill(Qt.lightGray)
        pixmap = pixmap.scaled(120, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pixmap = rounded_pixmap(pixmap, 16)  # Tambahkan border radius di sini
        img_label = QLabel()
        img_label.setPixmap(pixmap)
        img_label.setFixedSize(120, 200)
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setStyleSheet("background: transparent; margin-bottom: 5px;")
        layout.addWidget(img_label, alignment=Qt.AlignCenter)

        # Judul
        title = QLabel(book.get("title", ""))
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        title.setStyleSheet("""
            color: #7c4d9e;
            letter-spacing: 1px;
            background: transparent;
            border-radius: 10px;
            padding: 4px 12px;   /* Tambahkan padding agar kotak lebih besar */
        """)
        title.setWordWrap(True)  # Pastikan ini ada
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout.addWidget(title, alignment=Qt.AlignCenter)

        # Penulis, Tahun, Genre
        info_layout = QHBoxLayout()
        info_layout.setSpacing(18)  # Jarak antar info

        author = QLabel(f"👤 {book.get('authors', '-')}")
        author.setFont(QFont("Segoe UI", 10))
        author.setStyleSheet("color: #555; background: transparent;")
        info_layout.addWidget(author)

        year = "-"
        pub = book.get("publishedDate", "")
        if pub and len(pub) >= 4 and pub[:4].isdigit():
            year = pub[:4]
        year_label = QLabel(f"📅 {year}")
        year_label.setFont(QFont("Segoe UI", 10))
        year_label.setStyleSheet("color: #555; background: transparent;")
        info_layout.addWidget(year_label)

        genre = "-"
        cats = book.get("categories", "")
        if cats:
            genre = cats.split(",")[0]
        genre_label = QLabel(f"🏷️ {genre}")
        genre_label.setFont(QFont("Segoe UI", 10))
        genre_label.setStyleSheet("color: #555; background: transparent;")
        info_layout.addWidget(genre_label)

        layout.addLayout(info_layout)

        # Baris rating + ikon simpan & share
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        # Rating
        rating = book.get("rating", "N/A")
        rating_label = QLabel(f"⭐ {rating}")
        rating_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        rating_label.setStyleSheet("color: #ffb300; background: transparent; margin-bottom: 8px;")
        action_layout.addWidget(rating_label)

        from database import get_all_favorite_books
        fav_books = get_all_favorite_books()
        self.is_favorite = any(
            b[1] == book.get("title", "") and b[2] == book.get("authors", "") for b in fav_books
        )

        # Tombol simpan (bookmark)
        self.fav_btn = QPushButton()
        self.fav_btn.setToolTip("Simpan ke Favorit")
        self.fav_btn.setCursor(Qt.PointingHandCursor)
        self.fav_btn.setFixedSize(32, 32)
        self.fav_btn.setIconSize(QSize(24, 24))
        self.update_fav_btn_style()
        self.fav_btn.clicked.connect(self.handle_favorite)
        action_layout.addWidget(self.fav_btn)

        # Tombol share
        share_btn = QPushButton()
        share_btn.setToolTip("Bagikan Buku")
        share_btn.setCursor(Qt.PointingHandCursor)
        share_btn.setFixedSize(32, 32)
        share_btn.setIconSize(QSize(24, 24))
        share_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background: #f3e9f1;
                border-radius: 16px;
            }
        """)
        share_btn.setIcon(QIcon("share.png"))  # Pastikan file ada di folder project
        share_btn.clicked.connect(lambda: self.share_book(book))
        action_layout.addWidget(share_btn)

        layout.addLayout(action_layout)

        # Deskripsi
        desc_text = book.get("description", "")
        desc_label = QLabel(desc_text)
        desc_label.setWordWrap(True)
        desc_label.setFont(QFont("Segoe UI", 10))
        desc_label.setStyleSheet("""
            background: #fff;
            border-radius: 8px;
            padding: 10px 14px;
            color: #333;
        """)
        desc_label.setAlignment(Qt.AlignTop)

        desc_scroll = QScrollArea()
        desc_scroll.setWidgetResizable(True)
        desc_scroll.setFixedHeight(120)
        desc_scroll.setStyleSheet("background: transparent; border: none;")
        desc_scroll.setWidget(desc_label)
        layout.addWidget(desc_scroll)

        # Tombol Baca
        fullbook_url = book.get("fullbook", "")
        read_btn = QPushButton("Baca")
        read_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        read_btn.setCursor(Qt.PointingHandCursor)
        read_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c4d9e;
                color: white;
                border-radius: 10px;
                padding: 4px 12px;
                font-weight: bold;
                margin-bottom: 0px;
            }
            QPushButton:hover {
                background-color: #b89acb;
            }
        """)
        def open_fullbook():
            if fullbook_url:
                QDesktopServices.openUrl(QUrl(fullbook_url))
            else:
                QMessageBox.information(self, "Info", "Link buku tidak tersedia.")
        read_btn.clicked.connect(open_fullbook)

        # Tombol Tutup
        close_btn = QPushButton("Tutup")
        close_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #b89acb;
                color: white;
                border-radius: 10px;
                padding: 4px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7c4d9e;
            }
        """)
        close_btn.clicked.connect(on_close)

        # Layout horizontal untuk kedua tombol
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)
        btn_layout.addStretch()
        btn_layout.addWidget(read_btn)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def add_to_favorite(self, book):
        notes = f"{book.get('thumbnail','')}|{book.get('publishedDate','')}"
        add_favorite_book(
            book.get("title", ""),
            book.get("authors", ""),
            book.get("categories", ""),
            str(book.get("rating", "")),
            notes
        )
        QMessageBox.information(self, "Favorit", "Buku berhasil ditambahkan ke favorit!")

    def share_book(self, book):
            # Contoh: copy judul dan penulis ke clipboard
            text = f"{book.get('title', '')} oleh {book.get('authors', '')}"
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            QMessageBox.information(self, "Share", "Info buku telah disalin ke clipboard!")

    def update_fav_btn_style(self):
            if self.is_favorite:
                self.fav_btn.setIcon(QIcon("favorite_on.png"))  # Icon untuk sudah favorit
                self.fav_btn.setStyleSheet("""
                    QPushButton {
                        background: #f3e9f1;
                        border: none;
                        border-radius: 16px;
                    }
                """)
            else:
                self.fav_btn.setIcon(QIcon("favorite_off.png"))
                self.fav_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                    }
                    QPushButton:hover {
                        background: #f3e9f1;
                        border-radius: 16px;
                    }
                """)
    def handle_favorite(self):
            if self.is_favorite:
                QMessageBox.information(self, "Favorit", "Buku sudah ada di favorit!")
            else:
                self.add_to_favorite(self.book)
                self.is_favorite = True
                self.update_fav_btn_style()

class FavoriteBooksWidget(QWidget):
    def __init__(self, on_back, parent=None):
        super().__init__(parent)
        self.on_back = on_back
        self.setStyleSheet("background-color: #f3e9f1;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(10)

        title = QLabel("★ Daftar Buku Favorit")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            color: #7c4d9e;
            letter-spacing: 2px;
            margin-bottom: 18px;
            text-shadow: 0 2px 8px #e0d7ea;
        """)
        layout.addWidget(title)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(8)
        layout.addWidget(self.list_widget)

        # Tombol export
        export_layout = QHBoxLayout()
        export_layout.setSpacing(12)

        btn_export_pdf = QPushButton("⬇ Export PDF")
        btn_export_pdf.setFont(QFont("Segoe UI", 11, QFont.Bold))
        btn_export_pdf.setCursor(Qt.PointingHandCursor)
        btn_export_pdf.setFixedHeight(40)
        btn_export_pdf.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c4d9e, stop:1 #b89acb);
                color: #fff;
                border: none;
                border-radius: 20px;
                padding: 0 28px;
                font-size: 15px;
                letter-spacing: 1px;
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b89acb, stop:1 #7c4d9e);
            }
        """)
        btn_export_pdf.clicked.connect(self.handle_export_pdf)
        export_layout.addWidget(btn_export_pdf)

        btn_export_csv = QPushButton("⬇ Export CSV")
        btn_export_csv.setFont(QFont("Segoe UI", 11, QFont.Bold))
        btn_export_csv.setCursor(Qt.PointingHandCursor)
        btn_export_csv.setFixedHeight(40)
        btn_export_csv.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c4d9e, stop:1 #b89acb);
                color: #fff;
                border: none;
                border-radius: 20px;
                padding: 0 28px;
                font-size: 15px;
                letter-spacing: 1px;
                
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b89acb, stop:1 #7c4d9e);
            }
        """)
        btn_export_csv.clicked.connect(self.handle_export_csv)
        export_layout.addWidget(btn_export_csv)

        layout.addLayout(export_layout)

        # Tombol kembali
        back_btn = QPushButton("← Kembali")
        back_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.setFixedHeight(40)
        back_btn.setStyleSheet("""
            QPushButton {
                background: #fff;
                color: #7c4d9e;
                border: 2px solid #b89acb;
                border-radius: 20px;
                padding: 0 28px;
                font-size: 15px;
                letter-spacing: 1px;
                font-weight: bold;
                
            }
            QPushButton:hover {
                background: #f3e9f1;
                color: #a17abb;
                border: 2px solid #7c4d9e;
            }
        """)
        back_btn.clicked.connect(self.on_back)
        layout.addWidget(back_btn)

        # Scroll area untuk daftar favorit
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        fav_container = QWidget()
        fav_layout = QVBoxLayout(fav_container)
        fav_layout.setSpacing(18)
        fav_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(fav_container)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 1)

        self.fav_layout = fav_layout  # simpan untuk refresh

        self.refresh()

    # Pada refresh:
    def refresh(self):
        # Bersihkan list
        for i in reversed(range(self.fav_layout.count())):
            widget = self.fav_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # Ambil data favorit
        from database import get_all_favorite_books
        data = get_all_favorite_books()
        if not data:
            label = QLabel("Belum ada buku favorit.")
            label.setFont(QFont("Segoe UI", 12, QFont.Bold))
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("color: #b89acb;")
            self.fav_layout.addWidget(label)
        else:
            for row in data:
                # row: (id, title, authors, category, rating, notes)
                thumbnail, published = "", ""
                if row[5]:
                    parts = row[5].split("|")
                    thumbnail = parts[0] if len(parts) > 0 else ""
                    published = parts[1] if len(parts) > 1 else ""
                card = QWidget()
                card_layout = QHBoxLayout(card)
                card.setStyleSheet("""
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fff, stop:1 #f3e9f1);
                    border-radius: 18px;
                    border: none;
                """)
                card_layout.setContentsMargins(18, 12, 18, 12)
                card_layout.setSpacing(8)

                # Gambar di kiri
                img_label = QLabel()
                pixmap = QPixmap()
                if thumbnail:
                    try:
                        response = requests.get(thumbnail)
                        pixmap.loadFromData(response.content)
                    except Exception:
                        pixmap = QPixmap()
                if pixmap.isNull():
                    pixmap = QPixmap(100, 140)
                    pixmap.fill(Qt.lightGray)
                pixmap = pixmap.scaled(100, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                pixmap = rounded_pixmap(pixmap, 16)  # border radius lebih besar
                img_label.setPixmap(pixmap)
                img_label.setFixedSize(100, 140)
                img_label.setAlignment(Qt.AlignCenter)
                img_label.setStyleSheet("background: transparent; border: none;")  # Hapus border
                card_layout.addWidget(img_label)

                # Info buku di kanan
                info_layout = QVBoxLayout()
                info_layout.setSpacing(2)
                info_layout.setContentsMargins(0, 0, 0, 0)
                title = QLabel(f"{row[1]}")
                title.setFont(QFont("Segoe UI", 13, QFont.Bold))
                title.setStyleSheet("color: #7c4d9e; background: transparent; border: none;")
                title.setMaximumHeight(220)
                info_layout.addWidget(title)
                year_label = QLabel(f"📅 {published if published else '-'}")
                year_label.setFont(QFont("Segoe UI", 10))
                year_label.setStyleSheet("color: #555; background: transparent; border: none;")
                year_label.setMaximumHeight(220)
                info_layout.addWidget(year_label)
                author = QLabel(f"👤 {row[2]}")
                author.setFont(QFont("Segoe UI", 10))
                author.setStyleSheet("color: #555; background: transparent; border: none;")
                author.setMaximumHeight(220)
                info_layout.addWidget(author)
                genre = QLabel(f"🏷️ {row[3]}")
                genre.setFont(QFont("Segoe UI", 10))
                genre.setStyleSheet("color: #555; background: transparent; border: none;")
                genre.setMaximumHeight(220)
                info_layout.addWidget(genre)
                rating = QLabel(f"⭐ {row[4]}")
                rating.setFont(QFont("Segoe UI", 10, QFont.Bold))
                rating.setStyleSheet("color: #ffb300; background: transparent; border: none;")
                rating.setMaximumHeight(220)
                info_layout.addWidget(rating)

                info_container = QWidget()
                info_container.setLayout(info_layout)
                info_container.setMaximumHeight(220)
                card_layout.addWidget(info_container)
                

                # Tombol aksi di kanan bawah
                action_layout = QVBoxLayout()
                action_layout.addStretch()
                # Tombol hapus (save icon)
                remove_btn = QPushButton()
                remove_btn.setToolTip("Hapus dari Favorit")
                remove_btn.setCursor(Qt.PointingHandCursor)
                remove_btn.setFixedSize(32, 32)
                remove_btn.setIconSize(QSize(24, 24))
                remove_btn.setIcon(QIcon("favorite_on.png"))
                remove_btn.setStyleSheet("""
                    QPushButton {
                        background: #f3e9f1;
                        border: none;
                        border-radius: 16px;
                    }
                    QPushButton:hover {
                        background: #e0d7ea;
                    }
                """)
                remove_btn.clicked.connect(lambda _, book_id=row[0]: self.remove_favorite(book_id))
                action_layout.addWidget(remove_btn)

                # Tombol share
                share_btn = QPushButton()
                share_btn.setToolTip("Bagikan Buku")
                share_btn.setCursor(Qt.PointingHandCursor)
                share_btn.setFixedSize(32, 32)
                share_btn.setIconSize(QSize(24, 24))
                share_btn.setIcon(QIcon("share.png"))
                share_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                    }
                    QPushButton:hover {
                        background: #f3e9f1;
                        border-radius: 16px;
                    }
                """)
                share_btn.clicked.connect(lambda _, title=row[1], authors=row[2]: self.share_book(title, authors))
                action_layout.addWidget(share_btn)
                card_layout.addLayout(action_layout)
                self.fav_layout.addWidget(card)


    def handle_export_pdf(self):
        from database import get_all_favorite_books
        from export_utils import export_to_pdf
        data = get_all_favorite_books()
        if not data:
            QMessageBox.warning(self, "Peringatan", "Tidak ada data untuk diekspor.")
            return
        export_to_pdf("favorite_books.pdf", data)
        QMessageBox.information(self, "Sukses", "Data berhasil diekspor ke PDF.")

    def handle_export_csv(self):
        from database import get_all_favorite_books
        from export_utils import export_to_csv
        data = get_all_favorite_books()
        if not data:
            QMessageBox.warning(self, "Peringatan", "Tidak ada data untuk diekspor.")
            return
        export_to_csv("favorite_books.csv", data)
        QMessageBox.information(self, "Sukses", "Data berhasil diekspor ke CSV.")

    def remove_favorite(self, book_id):
        remove_favorite_book(book_id)
        QMessageBox.information(self, "Favorit", "Buku dihapus dari favorit.")
        self.refresh()

    def share_book(self, title, authors):
        text = f"{title} oleh {authors}"
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "Share", "Info buku telah disalin ke clipboard!")

class BookRecommenderApp(QMainWindow):
    def __init__(self, show_favorites_callback):
        super().__init__()
        self.show_favorites_callback = show_favorites_callback
        self.setWindowTitle("🌸 Aplikasi Rekomendasi Buku 🌸")
        self.setGeometry(200, 100, 800, 600)
        self.books = []
        self.filtered_books = []
        

        # Setup UI dan database
        self.init_ui()
        init_db()
        self.load_books("bestseller")
        self.active_filter = None
        self.active_filter_value = None
        self.filter_buttons = {}
        self.filter_value_buttons = {}




    def init_ui(self):
        pastel_bg = "#f3e9f1"
        pastel_btn = "#b89acb"
        pastel_btn_hover = "#a17abb"
        font_main = QFont("Segoe UI", 11)
        self.setStyleSheet(f"background-color: {pastel_bg}; font-family: 'Segoe UI';")

        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        help_menu = menubar.addMenu("Help")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        

        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(30, 20, 30, 20)
        main_layout.setSpacing(10)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Header aplikasi
        header_label = QLabel("HBOOK")
        header_label.setFont(QFont("Segoe UI", 28, QFont.Bold))
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("color: #7c4d9e; letter-spacing: 2px; margin-bottom: 8px;")
        main_layout.addWidget(header_label)

        # Search bar dengan efek radius
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Cari buku berdasarkan judul atau penulis...")
        self.search_input.setFont(font_main)
        self.search_input.setFixedHeight(38)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border-radius: 18px;
                border: 1.5px solid #b89acb;
                padding-left: 18px;
                padding-right: 18px;
                background: #fff;
                color: #333;
            }
            QLineEdit:focus {
                border: 2px solid #a17abb;
                background: #f7f3fa;
            }
        """)
        self.search_input.returnPressed.connect(self.handle_search_enter)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        # Filter bar
        filter_bar_widget = QWidget()
        filter_bar_layout = QHBoxLayout(filter_bar_widget)
        filter_bar_layout.setContentsMargins(0, 0, 0, 0)
        filter_bar_layout.setSpacing(8)

        # Tombol filter utama
        self.filter_menubar = QMenuBar()
        self.filter_menubar.setStyleSheet("""
            QMenuBar {
                background: #f3e9f1;
                border: none;
                font-size: 15px;
                color: #7c4d9e;
            }
            QMenuBar::item {
                background: #b89acb;
                color: white;
                border-radius: 16px;
                padding: 6px 18px;
                margin-right: 8px;
                font-weight: bold;
            }
            QMenuBar::item:selected {
                background: #7c4d9e;
                color: white;
            }
        """)
        self.filter_menu = self.filter_menubar.addMenu("Filter")
        self.filter_menu.setStyleSheet("background: #b89acb; color: white; border-radius: 16px;")
        self.filter_menu.addAction("Filter", lambda: self.set_filter_menu("Filter"))
        self.filter_menu.addAction("Tahun", lambda: self.set_filter_menu("Tahun"))
        self.filter_menu.addAction("Negara", lambda: self.set_filter_menu("Negara"))
        self.filter_menu.addAction("Genre", lambda: self.set_filter_menu("Genre"))
        self.filter_menu.addAction("Alphabet", lambda: self.set_filter_menu("Alphabet"))
        filter_bar_layout.addWidget(self.filter_menubar, 0)

        # Garis pemisah
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #bbb; background: #bbb; min-width:2px;")
        filter_bar_layout.addWidget(line, 0)

        # Scroll area untuk tombol filter value
        self.filter_value_scroll = QScrollArea()
        self.filter_value_scroll.setWidgetResizable(True)
        self.filter_value_scroll.setFixedHeight(30)
        self.filter_value_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.filter_value_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.filter_value_scroll.setFrameShape(QFrame.NoFrame)
        self.filter_value_widget = QWidget()
        self.filter_value_layout = QHBoxLayout(self.filter_value_widget)
        self.filter_value_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_value_layout.setSpacing(8)
        self.filter_value_scroll.setWidget(self.filter_value_widget)
        filter_bar_layout.addWidget(self.filter_value_scroll, 1)  # stretch=1 agar value filter memenuhi sisa ruang

        filter_bar_widget.setFixedHeight(35)
        main_layout.addWidget(filter_bar_widget)

        # Bungkus filter bar dalam widget agar bisa diatur lebar
        # filter_bar_widget = QWidget()
        # filter_bar_widget.setLayout(self.filter_bar)
        # filter_bar_widget.setFixedHeight(48)
        # main_layout.addWidget(filter_bar_widget)

        # Scroll area untuk grid buku
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.books_container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(10)  # Lebih rapat antar buku
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.books_container.setLayout(self.grid_layout)
        self.scroll_area.setWidget(self.books_container)
        main_layout.addWidget(self.scroll_area)

        # Tambahkan tombol lihat favorit
        self.btn_favorites = QPushButton("★ Lihat Favorit")
        self.btn_favorites.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.btn_favorites.setCursor(Qt.PointingHandCursor)
        self.btn_favorites.setFixedHeight(44)
        self.btn_favorites.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #b89acb, stop:1 #7c4d9e);
                color: #fff;
                border: none;
                border-radius: 22px;
                padding: 0 32px;
                letter-spacing: 1px;
                font-size: 16px;
                
                transition: background 0.2s;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7c4d9e, stop:1 #b89acb);
                color: #fff;
            }
        """)

        self.btn_favorites.clicked.connect(self.show_favorites_callback)

        # Tombol aksi
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_favorites)
        main_layout.addLayout(button_layout)

        self.main_split = QHBoxLayout()
        self.books_widget = QWidget()
        self.books_widget.setLayout(main_layout)  # main_layout dari grid buku & filter
        self.main_split.addWidget(self.books_widget, 1)
        self.detail_widget = None  # Panel detail, default None

        # Bungkus dalam widget utama
        container = QWidget()
        container.setLayout(self.main_split)
        self.setCentralWidget(container)

    def show_book_detail(self, book):
        if self.detail_widget:
            self.main_split.removeWidget(self.detail_widget)
            self.detail_widget.deleteLater()
            self.detail_widget = None
            return  # Tutup jika sudah terbuka

        self.detail_widget = BookDetailWidget(book, self.close_book_detail)
        self.main_split.addWidget(self.detail_widget, 0)

    def close_book_detail(self):
        if self.detail_widget:
            self.main_split.removeWidget(self.detail_widget)
            self.detail_widget.deleteLater()
            self.detail_widget = None

    def set_filter_menu(self, filter_type):
        self.filter_menu.setTitle(filter_type)
        self.show_filter_values(filter_type, True)

    
    def show_filter_values(self, filter_type, checked):
        # Reset semua tombol filter utama kecuali yang aktif
        for ftype, btn in self.filter_buttons.items():
            if ftype != filter_type:
                btn.setChecked(False)
        # Bersihkan filter value
        for i in reversed(range(self.filter_value_layout.count())):
            widget = self.filter_value_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.filter_value_buttons = {}

        if not checked:
            self.filter_menu.setTitle("Filter")
            self.active_filter = None
            self.active_filter_value = None
            self.load_books(self.search_input.text().strip() or "bestseller")
            return

        self.active_filter = filter_type
        self.active_filter_value = None

        # Ambil data filter value dari buku yang sudah di-load
        values = set()
        if filter_type == "Tahun":
            for book in self.books:
                # Tahun dari publishedDate, ambil 4 digit pertama
                pub = book.get("publishedDate", "")
                if pub and len(pub) >= 4 and pub[:4].isdigit():
                    values.add(pub[:4])
            values = sorted(values)
        elif filter_type == "Negara":
            # Google Books API tidak selalu menyediakan negara, jadi contoh: "language"
            for book in self.books:
                lang = book.get("language", "")
                if lang:
                    values.add(lang.upper())
            values = sorted(values)
        elif filter_type == "Genre":
            for book in self.books:
                cats = book.get("categories", "")
                for cat in cats.split(","):
                    cat = cat.strip()
                    if cat:
                        values.add(cat)
            values = sorted(values)
        elif filter_type == "Alphabet":
            for book in self.books:
                title = book.get("title", "")
                if title:
                    values.add(title[0].upper())
            values = sorted(values)

        # Buat tombol value
        for val in values:
            btn = QPushButton(val)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0d7ea;
                    color: #7c4d9e;
                    border-radius: 15px;
                    padding: 4px 22px;
                    font-weight: bold;
                    border: none;
                    min-width: 0px;
                    min-height: 0px;
                }
                QPushButton:checked {
                    background-color: #7c4d9e;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, v=val: self.apply_filter_value(v, checked))
            btn.setMinimumHeight(28)
            btn.setMaximumHeight(32)
            self.filter_value_layout.addWidget(btn)
            self.filter_value_buttons[val] = btn

    def apply_filter_value(self, value, checked):
        # Reset semua tombol value kecuali yang aktif
        for v, btn in self.filter_value_buttons.items():
            if v != value:
                btn.setChecked(False)
        if not checked:
            self.active_filter_value = None
            self.display_books(self.books)
            return
        self.active_filter_value = value
        # Filter buku sesuai filter aktif
        filtered = []
        if self.active_filter == "Tahun":
            for book in self.books:
                pub = book.get("publishedDate", "")
                if pub.startswith(value):
                    filtered.append(book)
        elif self.active_filter == "Negara":
            for book in self.books:
                lang = book.get("language", "").upper()
                if lang == value:
                    filtered.append(book)
        elif self.active_filter == "Genre":
            for book in self.books:
                cats = book.get("categories", "")
                if value in [c.strip() for c in cats.split(",")]:
                    filtered.append(book)
        elif self.active_filter == "Alphabet":
            for book in self.books:
                title = book.get("title", "")
                if title and title[0].upper() == value:
                    filtered.append(book)
        self.display_books(filtered)


    def show_about(self):
        QMessageBox.information(self, "About", "Aplikasi Rekomendasi Buku\nDibuat oleh Hendra Ahmad Yani")

    def load_books(self, query):
        # Ambil buku dari API
        self.books = search_books(query)
        self.filtered_books = self.books
        self.display_books(self.books)

    def display_books(self, books):
        # Bersihkan grid
        for i in reversed(range(self.grid_layout.count())):
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # Tampilkan buku dalam grid 5 kolom
        cols = 5
        for idx, book in enumerate(books):
            row = idx // cols
            col = idx % cols
            widget = BookWidget(book, parent=self)  # <-- tambahkan parent=self
            self.grid_layout.addWidget(widget, row, col)

    def handle_search_enter(self):
        query = self.search_input.text().strip()
        if not query:
            self.load_books("bestseller")
        else:
            self.load_books(query)  # delay 400ms

    def handle_export_pdf(self):
        data = get_all_favorite_books()
        if not data:
            QMessageBox.warning(self, "Peringatan", "Tidak ada data untuk diekspor.")
            return
        export_to_pdf("favorite_books.pdf", data)
        QMessageBox.information(self, "Sukses", "Data berhasil diekspor ke PDF.")

    def handle_export_csv(self):
        data = get_all_favorite_books()
        if not data:
            QMessageBox.warning(self, "Peringatan", "Tidak ada data untuk diekspor.")
            return
        export_to_csv("favorite_books.csv", data)
        QMessageBox.information(self, "Sukses", "Data berhasil diekspor ke CSV.")

class WelcomeScreen(QWidget):
    def __init__(self, on_start, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Selamat Datang")
        self.setStyleSheet("background-color: #f3e9f1;")

        # Layout utama (agar konten benar-benar di tengah)
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)

        # Widget container untuk logo dan tombol
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setAlignment(Qt.AlignCenter)
        center_layout.setSpacing(25)

        # Logo aplikasi
        logo_label = QLabel()
        pixmap = QPixmap("logo.png")
        if pixmap.isNull():
            logo_label.setText("Logo tidak ditemukan")
            logo_label.setAlignment(Qt.AlignCenter)
        else:
            pixmap = pixmap.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
        center_layout.addWidget(logo_label, alignment=Qt.AlignCenter)

        # Tombol Mulai
        start_btn = QPushButton("Mulai")
        start_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.setFixedWidth(160)
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #b89acb;
                color: white;
                padding: 12px 24px;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #f3e9f1;
            }
        """)
        start_btn.clicked.connect(on_start)
        center_layout.addWidget(start_btn, alignment=Qt.AlignCenter)

        main_layout.addWidget(center_widget, alignment=Qt.AlignCenter)

        # Tambahkan stretch agar status bar selalu di bawah
        main_layout.addStretch(1)
        main_layout.addWidget(center_widget, alignment=Qt.AlignCenter)
        main_layout.addStretch(1)

        # QStatusBar di bawah, lebar penuh, teks tengah
        status_bar = QStatusBar()
        status_bar.setStyleSheet("""
            QStatusBar {
                font-size: 14px;
                font-family: 'Segoe UI', Arial, sans-serif;
                letter-spacing: 1.5px;
                padding: 8px 0 8px 0;
                background: #f3e9f1;
                border-top: 1.5px solid #f3e9f1;
            }
        """)
        copyright_label = QLabel("© 2025 Hendra Ahmad Yani | F1D022122 | All Rights Reserved")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #7c4d9e;")
        status_bar.addPermanentWidget(copyright_label, 1)  # stretch=1 agar di tengah

        main_layout.addWidget(status_bar)

        self.setLayout(main_layout)
        # self.setFixedSize(800, 600)

class MainStack(QStackedWidget):
    def __init__(self):
        super().__init__()
        self.welcome = WelcomeScreen(self.show_main)
        self.main_window = BookRecommenderApp(self.show_favorites)
        self.favorites_widget = FavoriteBooksWidget(self.show_main)
        self.addWidget(self.welcome)         # index 0
        self.addWidget(self.main_window)     # index 1
        self.addWidget(self.favorites_widget) # index 2
        self.setCurrentIndex(0)

    def show_main(self):
        self.setCurrentIndex(1)

    def show_favorites(self):
        self.favorites_widget.refresh()
        self.setCurrentIndex(2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    stack = MainStack()
    stack.setWindowTitle("Aplikasi Rekomendasi Buku")
    stack.resize(800, 600)
    stack.show()
    sys.exit(app.exec_())
