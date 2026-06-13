from __future__ import annotations

import hashlib
import re
from pathlib import Path

from app.chunker import TextChunk, chunk_text
from app.database import save_document
from app.document_parser import parse_document
from app.embedding import embed_query, embed_texts, generate_answer
from app.pinecone_client import query_vectors, upsert_vectors


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)

    return value.strip("-") or "document"


def make_doc_id(title: str, filename: str) -> str:
    digest = hashlib.sha1(f"{title}:{filename}".encode("utf-8")).hexdigest()[:10]

    return f"{slugify(title)}-{digest}"


def build_vectors(
    chunks: list[TextChunk],
    embeddings: list[list[float]],
    doc_id: str,
    title: str,
    category: str,
    source_file: str,
) -> list[dict]:
    vectors = []

    for chunk, vector in zip(chunks, embeddings):
        vector_id = f"{doc_id}::chunk-{chunk.chunk_index}"

        vectors.append(
            {
                "id": vector_id,
                "values": vector,
                "metadata": {
                    "doc_id": doc_id,
                    "title": title,
                    "category": category,
                    "source_file": source_file,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number or 0,
                    "text": chunk.text,
                },
            }
        )

    return vectors


def ingest_document(
    file_path: str | Path,
    title: str,
    category: str,
    namespace: str,
    original_filename: str,
    user_id: int,
) -> dict:
    text = parse_document(file_path)
    chunks = chunk_text(text)

    if not chunks:
        raise ValueError("The uploaded document did not contain extractable text.")

    doc_id = make_doc_id(title, original_filename)

    embeddings = embed_texts([chunk.text for chunk in chunks])

    vectors = build_vectors(
        chunks=chunks,
        embeddings=embeddings,
        doc_id=doc_id,
        title=title,
        category=category,
        source_file=original_filename,
    )

    upsert_vectors(
        vectors=vectors,
        namespace=namespace,
    )

    save_document(
        doc_id=doc_id,
        title=title,
        category=category,
        namespace=namespace,
        source_file=original_filename,
        chunk_count=len(chunks),
        user_id=user_id,
    )

    return {
        "doc_id": doc_id,
        "title": title,
        "category": category,
        "namespace": namespace,
        "source_file": original_filename,
        "chunk_count": len(chunks),
    }


def make_metadata_filter(
    category: str | None = None,
    title: str | None = None,
) -> dict | None:
    filters = {}

    if category:
        filters["category"] = {"$eq": category}

    if title:
        filters["title"] = {"$eq": title}

    return filters or None


def search_documents(
    question: str,
    namespace: str,
    category: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    vector = embed_query(question)

    metadata_filter = make_metadata_filter(category=category)

    return query_vectors(
        vector=vector,
        namespace=namespace,
        top_k=top_k,
        metadata_filter=metadata_filter,
    )


def answer_question(
    question: str,
    namespace: str,
    category: str | None = None,
    top_k: int = 5,
) -> dict:
    matches = search_documents(
        question=question,
        namespace=namespace,
        category=category,
        top_k=top_k,
    )

    contexts = [match["metadata"] for match in matches]

    answer = generate_answer(
        question=question,
        contexts=contexts,
    )

    return {
        "question": question,
        "answer": answer,
        "matches": matches,
        "namespace": namespace,
        "category": category or "",
        "top_k": top_k,
    }