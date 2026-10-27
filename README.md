# HBook — Book Discovery

**SOFTWARE** | **DESKTOP APPLICATION** | **PYTHON ‧ SQLITE**

HBook is a desktop application designed to help users discover books, explore available book information, and manage personal reading collections. The application integrates with the Open Library API to retrieve book metadata and cover images, while providing search, filtering, favorites management, and CSV/PDF export features through a pastel-themed interface.

## 01. Project Overview

**HBook** is a desktop-based book discovery and collection management application developed to simplify the process of finding, exploring, and organizing books.

### Objectives
- Simplify book discovery through keyword-based searches.
- Present available book metadata in an organized interface.
- Help users manage personal reading lists through a favorites feature.
- Support book collection organization through filtering and sorting.
- Provide export functionality for documenting saved book collections.

### Problem Statement

Finding relevant books and organizing reading preferences can become inconvenient when users must search across multiple sources and maintain their own lists separately. Book information may also be incomplete or presented inconsistently across different records.

### Solution

HBook integrates the Open Library API with a desktop interface and a local SQLite database. Users can search for books, view available metadata, save favorites, filter and sort results, and export their saved collections.

The application also implements local caching to reuse previous search results and reduce repeated API requests.

### Key Outcomes
- Centralized book discovery through a single desktop application.
- Organized book information, including titles, authors, publication years, categories, languages, ratings, and cover images when available.
- Persistent storage for favorite books.
- Exportable favorite collections in CSV and PDF formats.
- Easier browsing through filtering and sorting options.

## 02. Tech Stack

| Category | Technology |
|---|---|
| Programming Language | Python |
| Desktop GUI Framework | PyQt5 |
| Local Database | SQLite |
| External API | Open Library API |
| HTTP Requests | Requests |
| Image Processing | PyQt5 QImage and QPixmap |
| Data Export | CSV, FPDF |
| Development Tools | Git, GitHub |

## 03. Screenshots / Results

### Application Workflow

1. **Welcome Page** — Introduces HBook and provides access to the book catalog.
2. **Book Catalog** — Displays search results with book covers and basic metadata.
3. **Search and Filtering** — Allows users to search by title or author and browse results by publication year, language, genre, or alphabet.
4. **Book Details** — Displays available information about a selected book and provides actions to save favorites, share information, or open its Open Library page.
5. **Favorites Collection** — Displays saved books stored in the local SQLite database.
6. **Export** — Exports the favorite collection to CSV or PDF.

### Application Screenshots

**Welcome Page**

<img width="851" height="611" alt="image" src="https://github.com/user-attachments/assets/f51cfd5c-9756-4cb8-a88b-031985960f23" />


**Book Catalog**

<img width="850" height="599" alt="image" src="https://github.com/user-attachments/assets/fabb8475-5527-4d83-a388-3f50ad774503" />

**Search Books**

<img width="850" height="602" alt="image" src="https://github.com/user-attachments/assets/edef4f42-70a5-4bb1-b6fc-261b487953dd" />

**Filter Books**

<img width="851" height="598" alt="image" src="https://github.com/user-attachments/assets/8a451ff5-eccc-4790-b51e-5397a9495f90" />

**Book Details**

<img width="848" height="592" alt="image" src="https://github.com/user-attachments/assets/fac0d71a-c621-4da8-bbb8-58de90e892bc" />

**Favorites Collection**

<img width="850" height="594" alt="image" src="https://github.com/user-attachments/assets/31d96605-479a-4dcc-88e2-95097a8fde15" />


### Insight

HBook organizes book metadata from the Open Library catalog into a consistent interface. Users can explore available publication information, identify books by title or author, and browse collections using metadata-based filters.

The application also demonstrates how an external book API can be integrated with local data storage to support a personalized reading collection.

### Usefulness

- Reduces the effort required to search for and organize books.
- Helps users maintain a reusable collection of favorite books.
- Makes book information easier to browse and compare.
- Provides exportable records for personal documentation and collection management.

### Practical Application

HBook can be used as a personal book discovery tool, a reading-list organizer, or a small-scale desktop catalog for users who want to collect and document books of interest.

**Note:** The availability and completeness of book metadata depend on the records provided by Open Library. The application does not guarantee that every book has a description, rating, publication date, or cover image.

## 04. Installation & Usage

### Prerequisites

- Python 3.9 or newer.
- An internet connection for new searches and remote cover images.
- Git, if cloning the repository.

### Project Structure

```text
app-HBook/
├── Asset/
│   ├── back.png
│   ├── csv.png
│   ├── export.png
│   ├── favorite_off.png
│   ├── favorite_on.png
│   ├── logo.png
│   ├── pdf.png
│   └── share.png
├── data/
│   ├── books.db
│   └── books_cache/
├── export/
│   ├── favorite_books.csv
│   └── favorite_books.pdf
├── api_openlibrary.py
├── database.py
├── export_utils.py
├── main.py
└── README.md
```

### Installation

**1. Clone the repository**

```bash
git clone <GITHUB_REPOSITORY_URL>
cd app-HBook
```

Replace `<GITHUB_REPOSITORY_URL>` with the actual repository URL.

**2. Install dependencies**

```bash
pip install PyQt5 requests fpdf
```

If the project uses additional packages or a specific FPDF version, include them in the dependency configuration.

**3. Configure the application**

- Ensure the `Asset/` directory contains the required interface assets.
- Ensure the application can create or access the `data/` directory.
- Keep `api_openlibrary.py`, `database.py`, `export_utils.py`, and `main.py` in the project root.
- An Open Library API key is not required for basic search requests.

**4. Run the application**

```bash
python main.py
```

### Usage

1. Launch HBook and open the catalog.
2. Enter a book title, author name, or keyword in the search field.
3. Browse the available results and apply filters as needed.
4. Select a book to view its details.
5. Save books to your favorites collection.
6. Open the favorites page to review saved books.
7. Export your favorite collection to CSV or PDF.

### Data Storage

- `data/books.db` stores favorite book records using SQLite.
- `data/books_cache/` stores cached search results.
- `export/` is intended for generated CSV and PDF files.
- `Asset/` contains images and icons used by the interface.

### Notes

- Cached results may be reused when available, but offline access is not guaranteed for every search.
- New searches and remote cover images require internet access.
- Avoid committing personal database contents or generated exports if they contain private information.
- Verify the application and its export features before publishing the repository.

