"""
RAG Retriever: Embeds a query and retrieves the most relevant context from ChromaDB.
Used by the Review Agent to ground resume scoring in historical hiring knowledge.
"""
import os
from openai import OpenAI
from dotenv import load_dotenv
from rag.setup import get_or_create_collection, EMBEDDING_MODEL

load_dotenv()

_openai_client: OpenAI | None = None
_collection = None


def _get_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _openai_client


def _get_collection():
    global _collection
    if _collection is None:
        _collection = get_or_create_collection()
    return _collection


def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """
    Embed the query and retrieve the top-k most relevant chunks.

    Args:
        query: The text to embed and search for (e.g., resume + job description).
        top_k: Number of results to retrieve.

    Returns:
        List of dicts with 'text', 'source', and 'score' keys.
    """
    client = _get_client()
    collection = _get_collection()

    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query]
    )
    query_embedding = response.data[0].embedding

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    retrieved = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        retrieved.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "similarity_score": round(1 - dist, 4)
        })

    return retrieved


def format_context_for_prompt(retrieved_chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a readable context block for injection into agent prompts.
    """
    if not retrieved_chunks:
        return "No relevant context retrieved from knowledge base."

    sections = []
    for i, chunk in enumerate(retrieved_chunks, 1):
        sections.append(
            f"[Context {i} | Source: {chunk['source']} | Relevance: {chunk['similarity_score']}]\n"
            f"{chunk['text']}"
        )
    return "\n\n---\n\n".join(sections)


def retrieve_and_format(query: str, top_k: int = 5) -> str:
    """
    Convenience function: retrieve relevant chunks and return them as a formatted string.
    """
    chunks = retrieve_context(query, top_k=top_k)
    return format_context_for_prompt(chunks)
