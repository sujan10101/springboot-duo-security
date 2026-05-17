"""
RAG Setup: Embeds the hiring knowledge corpus and stores it in ChromaDB.
Run this script once before starting the application to initialize the vector store.
"""
import os
import re
import chromadb
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_DIR = Path(__file__).parent / "documents"
CHROMA_PERSIST_DIR = Path(__file__).parent.parent / "chroma_db"
COLLECTION_NAME = "hiring_knowledge"
EMBEDDING_MODEL = "text-embedding-3-small"


def chunk_by_paragraph(text: str, min_chars: int = 100) -> list[str]:
    """Split text into paragraph-level chunks, filtering out very short ones."""
    paragraphs = re.split(r"\n{2,}", text.strip())
    chunks = []
    for para in paragraphs:
        cleaned = para.strip()
        if len(cleaned) >= min_chars:
            chunks.append(cleaned)
    return chunks


def load_documents() -> list[dict]:
    """Load all .txt files from the documents directory."""
    docs = []
    for doc_path in sorted(DOCUMENTS_DIR.glob("*.txt")):
        text = doc_path.read_text(encoding="utf-8")
        chunks = chunk_by_paragraph(text)
        for i, chunk in enumerate(chunks):
            docs.append({
                "text": chunk,
                "source": doc_path.name,
                "chunk_index": i,
                "id": f"{doc_path.stem}__chunk_{i}"
            })
    return docs


def embed_texts(texts: list[str], client: OpenAI) -> list[list[float]]:
    """Embed a list of texts using OpenAI text-embedding-3-small."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def setup_rag(force_rebuild: bool = False) -> chromadb.Collection:
    """
    Initialize ChromaDB collection with the hiring knowledge corpus.
    Skips rebuilding if the collection already exists unless force_rebuild=True.
    """
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
    existing = [c.name for c in chroma_client.list_collections()]

    if COLLECTION_NAME in existing and not force_rebuild:
        print(f"[RAG] Collection '{COLLECTION_NAME}' already exists. Skipping rebuild.")
        return chroma_client.get_collection(COLLECTION_NAME)

    if COLLECTION_NAME in existing:
        chroma_client.delete_collection(COLLECTION_NAME)
        print(f"[RAG] Deleted existing collection '{COLLECTION_NAME}' for rebuild.")

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    documents = load_documents()

    if not documents:
        raise FileNotFoundError(
            f"No documents found in {DOCUMENTS_DIR}. "
            "Please ensure the rag/documents/ directory contains .txt files."
        )

    print(f"[RAG] Embedding {len(documents)} chunks from {DOCUMENTS_DIR.name}/...")

    batch_size = 50
    for i in range(0, len(documents), batch_size):
        batch = documents[i: i + batch_size]
        texts = [doc["text"] for doc in batch]
        embeddings = embed_texts(texts, openai_client)

        collection.add(
            ids=[doc["id"] for doc in batch],
            documents=texts,
            embeddings=embeddings,
            metadatas=[{"source": doc["source"], "chunk_index": doc["chunk_index"]} for doc in batch]
        )
        print(f"[RAG] Embedded chunks {i + 1}–{min(i + batch_size, len(documents))}/{len(documents)}")

    print(f"[RAG] Setup complete. {len(documents)} chunks stored in '{COLLECTION_NAME}'.")
    return collection


def get_or_create_collection() -> chromadb.Collection:
    """Get the ChromaDB collection, creating it if it doesn't exist."""
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
    existing = [c.name for c in chroma_client.list_collections()]
    if COLLECTION_NAME not in existing:
        return setup_rag()
    return chroma_client.get_collection(COLLECTION_NAME)


if __name__ == "__main__":
    setup_rag(force_rebuild=True)
