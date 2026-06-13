from __future__ import annotations

from pathlib import Path
from pypdf import PdfReader


def parse_txt_or_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            parts.append(f"\n\n[Page {page_num}]\n{text.strip()}")

    return "\n".join(parts).strip()


def parse_document(path: str | Path) -> str:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return parse_pdf(file_path)

    if suffix in {".txt", ".md", ".markdown"}:
        return parse_txt_or_md(file_path)

    raise ValueError(
        f"Unsupported file type: {suffix}. Upload PDF, TXT, MD, or Markdown files."
    )