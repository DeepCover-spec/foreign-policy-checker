"""Extract text from a PDF with PyMuPDF (better word spacing than pypdf for some PDFs).

Usage (from the project root):
    python src\\treaty_checker\\extract_mupdf.py data\\raw\\crpd.pdf data\\raw\\crpd.txt

Install once:  pip install pymupdf
"""
import sys
from pathlib import Path

import pymupdf  # PyMuPDF


def pdf_to_text(pdf_path: str) -> str:
    with pymupdf.open(pdf_path) as doc:
        return "\n".join(page.get_text("text") for page in doc)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Usage: extract_mupdf.py PDF_PATH OUTPUT_TXT")
    text = pdf_to_text(sys.argv[1])
    Path(sys.argv[2]).write_text(text, encoding="utf-8")
    print(f"{len(text)} characters written to {sys.argv[2]}")