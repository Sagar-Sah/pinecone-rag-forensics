from __future__ import annotations

import time
from typing import Any

from pinecone import Pinecone, ServerlessSpec

from app.config import settings

pc = Pinecone(api_key=settings.pinecone_api_key)


def _index_names() -> list[str]:
    listed = pc.list_indexes()

    if hasattr(listed, "names"):
        return list(listed.names())

    return [str(getattr(item, "name", item)) for item in listed]


def _index_is_ready(index_name: str) -> bool:
    description = pc.describe_index(index_name)
    status = getattr(description, "status", None)

    if isinstance(status, dict):
        return bool(status.get("ready"))

    return bool(getattr(status, "ready", False))


def ensure_index() -> Any:
    """
    Creates the Pinecone serverless dense-vector index if it does not exist.

    Default dimension:
    text-embedding-3-small = 1536 dimensions.
    """

    index_name = settings.pinecone_index_name
    existing_names = _index_names()

    if index_name not in existing_names:
        pc.create_index(
            name=index_name,
            dimension=settings.embedding_dimension,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region,
            ),
        )

        # Serverless index creation can take a short time.
        for _ in range(60):
            if _index_is_ready(index_name):
                break

            time.sleep(1)

    return pc.Index(index_name)


def upsert_vectors(vectors: list[dict], namespace: str) -> None:
    if not vectors:
        return

    index = ensure_index()

    batch_size = 100

    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]

        index.upsert(
            vectors=batch,
            namespace=namespace,
        )


def query_vectors(
    vector: list[float],
    namespace: str,
    top_k: int = 5,
    metadata_filter: dict | None = None,
) -> list[dict]:
    index = ensure_index()

    result = index.query(
        vector=vector,
        namespace=namespace,
        top_k=top_k,
        include_metadata=True,
        filter=metadata_filter or None,
    )

    matches = []

    for match in result.matches or []:
        metadata = dict(match.metadata or {})

        matches.append(
            {
                "id": match.id,
                "score": float(match.score or 0),
                "metadata": metadata,
            }
        )

    return matches


def get_index_stats() -> dict:
    try:
        index = ensure_index()
        stats = index.describe_index_stats()

        if hasattr(stats, "to_dict"):
            return stats.to_dict()

        return dict(stats)

    except Exception as exc:
        return {"error": str(exc)}