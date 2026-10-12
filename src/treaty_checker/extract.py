from pathlib import Path

from pypdf import PdfReader


def pdf_to_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


if __name__ == "__main__":
    text = pdf_to_text("data/raw/ccpr.pdf")
    Path("data/raw/ccpr.txt").write_text(text, encoding="utf-8")
    print(len(text), "characters written to data/raw/ccpr.txt")