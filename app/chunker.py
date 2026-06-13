from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page_number: int | None = None


def clean_text(text: str) -> str:
    text = text.replace("\x00"," ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}","\n\n", text)

    return text.strip()


def _page_for_position(text: str, position: int) -> int | None:
    page_matches = list(
        re.finditer(
            r"\[Page\s+(\d+)\]",
            text[: position + 1],
            flags=re.I,
        )
    )

    if not page_matches:
        return None

    return int(page_matches[-1].group(1))



def chunk_text(
        text: str,
        chunk_size: int = 1400,
        overlap: int = 220,
) -> list[TextChunk]:
    text = clean_text(text)
    chunks: list[TextChunk] = []

    if not text:
        return chunks
    
    start = 0
    chunk_index = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end]

        #Try not to cut sentences in half
        if end < text_len:
            sentence_break = max(
                chunk.rfind(". "),
                chunk.rfind("? "),
                chunk.rfind("! "),
                chunk.rfind("\n\n"),
            )

            if sentence_break > chunk_size * 0.55:
                end = start + sentence_break +1
                chunk = text[start:end]
        
        chunk = chunk.strip()

        if chunk:
            chunks.append(
                TextChunk(
                    text=chunk,
                    chunk_index=chunk_index,
                    page_number=_page_for_position(text, start),
                )
            )
            chunk_index +=1

        if end >= text_len:
            break

        start = max(end - overlap, 0)

    return chunks
    