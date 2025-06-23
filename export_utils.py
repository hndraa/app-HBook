import csv
from fpdf import FPDF
import os

def export_to_csv(filename, data):
    if not data:
        return
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Title', 'Authors', 'Category', 'Rating', 'Notes'])
        for row in data:
            writer.writerow(row[1:])

def export_to_pdf(filename, data):
    if not data:
        return
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Laporan Buku Favorit", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", size=12)
    for row in data:
        title = row[1]
        authors = row[2]
        category = row[3]
        rating = row[4]
        notes = row[5]

        pdf.multi_cell(0, 10, f"Judul: {title}")
        pdf.multi_cell(0, 10, f"Penulis: {authors}")
        pdf.multi_cell(0, 10, f"Kategori: {category}")
        pdf.multi_cell(0, 10, f"Rating: {rating}")
        pdf.multi_cell(0, 10, f"Catatan: {notes}")
        pdf.ln(5)

    pdf.output(filename)
