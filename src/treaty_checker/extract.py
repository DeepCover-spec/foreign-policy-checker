import sys
from pathlib import Path

from pypdf import PdfReader


def pdf_to_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "data/raw/ccpr.pdf"
    out_path = sys.argv[2] if len(sys.argv) > 2 else str(Path(pdf_path).with_suffix(".txt"))
    text = pdf_to_text(pdf_path)
    Path(out_path).write_text(text, encoding="utf-8")
    print(len(text), "characters written to", out_path)