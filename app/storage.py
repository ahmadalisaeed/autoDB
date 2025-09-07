from __future__ import annotations
import os
import io
import uuid
from typing import List, Dict, Any, Tuple
import pandas as pd
from chromadb import Client
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from sqlalchemy.orm import Session
from .db import Document
from .utils import rows_to_text, robust_json_dump

PERSIST_DIR = os.getenv("AUTODB_CHROMA_DIR", "./chroma_store")
os.makedirs(PERSIST_DIR, exist_ok=True)

embedder = SentenceTransformerEmbeddingFunction(model_name=os.getenv("AUTODB_EMBED_MODEL", "all-MiniLM-L6-v2"))
chroma = Client(Settings(is_persistent=True, persist_directory=PERSIST_DIR))
collection = chroma.get_or_create_collection(name="autodb", embedding_function=embedder)


def _store_chunks(doc_id, source, chunks):
    ids = []
    texts = []
    metadatas = []
    for i, (text, json_blob) in enumerate(chunks):
        chunk_id = f"{doc_id}_{i}"
        ids.append(chunk_id)
        texts.append(text)
        metadatas.append({
            "doc_id": doc_id,
            "source": source or "unknown",
            "json": json_blob or ""
        })
    collection.add(ids=ids, documents=texts, metadatas=metadatas)


def save_text(db: Session, text: str, filename: str | None, metadata: Dict[str, Any] | None) -> Tuple[str, int]:
    doc_id = str(uuid.uuid4())
    d = Document(id=doc_id, filename=filename or "text_input.txt", content_type="text/plain")
    db.add(d)
    db.commit()
    _store_chunks(doc_id, d.filename, [(text, None)])
    return doc_id, 1


def save_json(db: Session, data: Any, filename: str | None) -> Tuple[str, int]:
    doc_id = str(uuid.uuid4())
    d = Document(id=doc_id, filename=filename or "data.json", content_type="application/json")
    db.add(d)
    db.commit()

    # Normalize: if the payload is a list of objects, embed each row; else embed whole object
    chunks: List[Tuple[str, str]] = []
    if isinstance(data, list) and data and isinstance(data[0], dict):
        for row in data:
            text = rows_to_text([row])[0]
            chunks.append((text, robust_json_dump(row)))
    elif isinstance(data, dict):
        text = rows_to_text([data])[0]
        chunks.append((text, robust_json_dump(data)))
    else:
        text = str(data)
        chunks.append((text, robust_json_dump(data)))

    _store_chunks(doc_id, d.filename, chunks)
    return doc_id, len(chunks)


def save_csv_bytes(db: Session, file_bytes: bytes, filename: str | None) -> Tuple[str, int]:
    doc_id = str(uuid.uuid4())
    d = Document(id=doc_id, filename=filename or "data.csv", content_type="text/csv")
    db.add(d)
    db.commit()

    df = pd.read_csv(io.BytesIO(file_bytes))
    rows = df.to_dict(orient="records")
    texts = rows_to_text(rows)
    chunks = list(zip(texts, [robust_json_dump(r) for r in rows]))
    _store_chunks(doc_id, d.filename, chunks)
    return doc_id, len(chunks)


def search_matches(query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    results = collection.query(query_texts=[query], n_results=top_k)
    matches = []
    sources = []
    # chroma returns lists; flatten
    for i in range(len(results.get("ids", [[]])[0])):
        matches.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": results["metadatas"][0][i].get("source"),
            "json": results["metadatas"][0][i].get("json"),
            "doc_id": results["metadatas"][0][i].get("doc_id"),
        })
        sources.append(results["metadatas"][0][i].get("source")) 
    return matches, sources