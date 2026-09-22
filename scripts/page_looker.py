import sys
import pdfplumber

PDF_PATH = "data/raw/mp-materials_10k_FY2025.pdf"
PAGE_OFFSET = 4  # in this file, pdf page = printed page + 4

printed_page = int(sys.argv[1])
pdf_page = printed_page + PAGE_OFFSET

with pdfplumber.open(PDF_PATH) as pdf:
    page = pdf.pages[pdf_page - 1]  # pdfplumber counts pages from 0
    print(f"--- printed page {printed_page} (pdf page {pdf_page}) ---")
    print(page.extract_text())