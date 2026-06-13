from __future__ import annotations

from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    
    response =  client.embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )

    return [item.embedding for item in response.data]

def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]



def generate_answer(question: str, contexts: list[dict]) -> str:
    if not contexts:
        return "I could not find enough relevant source material to answer that."

    context_text = "\n\n".join(
        [
            f"SOURCE {i + 1}: {ctx.get('title', 'Untitled')} | "
            f"File: {ctx.get('source_file', 'unknown')} | "
            f"Chunk: {ctx.get('chunk_index', 'unknown')} | "
            f"Page: {ctx.get('page_number', 'N/A')}\n"
            f"{ctx.get('text', '')}"
            for i, ctx in enumerate(contexts)
        ]
    )

    system_prompt = (
        "You are a precise RAG assistant. "
        "Answer only from the provided sources. "
        "If the sources do not contain the answer, say that clearly. "
        "Cite sources inline like [Source 1], [Source 2]. "
        "Keep the answer concise."
    )

    user_prompt = f"""
Question:
{question}

Sources:
{context_text}
""".strip()

    response = client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.1,
    )

    return response.choices[0].message.content or "No answer generated."