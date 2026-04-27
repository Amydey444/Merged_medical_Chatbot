import os
import json
import uuid
from datetime import datetime

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")

RAG_DIR = "rag_store"
INDEX_FILE = os.path.join(RAG_DIR, "medical.index")
META_FILE = os.path.join(RAG_DIR, "metadata.json")

os.makedirs(RAG_DIR, exist_ok=True)


def chunk_text(text, chunk_size=500, overlap=80):
    text = (text or "").strip()
    if not text:
        return []

    chunks = []
    start = 0
    step = max(1, chunk_size - overlap)

    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step

    return chunks


def load_metadata():
    if os.path.exists(META_FILE):
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_metadata(metadata):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def get_or_create_index(dim):
    if os.path.exists(INDEX_FILE):
        return faiss.read_index(INDEX_FILE)
    return faiss.IndexFlatL2(dim)


def add_to_rag(text, username="guest", source="image_analysis", extra=None):
    chunks = chunk_text(text)
    if not chunks:
        return 0

    embeddings = EMBED_MODEL.encode(chunks, convert_to_numpy=True).astype("float32")
    index = get_or_create_index(embeddings.shape[1])
    metadata = load_metadata()

    doc_id = str(uuid.uuid4())
    start_idx = len(metadata)

    index.add(embeddings)

    for i, chunk in enumerate(chunks):
        metadata.append({
            "doc_id": doc_id,
            "username": username,
            "source": source,
            "text": chunk,
            "extra": extra or {},
            "created_at": datetime.utcnow().isoformat(),
            "vector_row": start_idx + i
        })

    faiss.write_index(index, INDEX_FILE)
    save_metadata(metadata)
    return len(chunks)


def retrieve_chunks(query, username="guest", top_k=4, source=None):
    if not os.path.exists(INDEX_FILE):
        return []

    metadata = load_metadata()
    if not metadata:
        return []

    index = faiss.read_index(INDEX_FILE)

    query_vec = EMBED_MODEL.encode([query], convert_to_numpy=True).astype("float32")
    search_k = min(max(top_k * 5, top_k), len(metadata))
    distances, indices = index.search(query_vec, search_k)

    results = []
    for idx in indices[0]:
        if idx < 0 or idx >= len(metadata):
            continue

        item = metadata[idx]

        if item.get("username") != username:
            continue

        if source and item.get("source") != source:
            continue

        results.append(item)

        if len(results) >= top_k:
            break

    return results


def build_context(query, username="guest", top_k=4, source=None):
    results = retrieve_chunks(
        query=query,
        username=username,
        top_k=top_k,
        source=source
    )
    context = "\n\n".join([r["text"] for r in results])
    return context, results


def load_medical_kb_to_rag(username="guest"):
    kb_file = "medical_kb.json"

    if not os.path.exists(kb_file):
        return {"status": "error", "message": "medical_kb.json not found"}

    try:
        with open(kb_file, "r", encoding="utf-8") as f:
            kb_data = json.load(f)

        added = 0

        if isinstance(kb_data, list):
            for item in kb_data:
                text = json.dumps(item, ensure_ascii=False, indent=2)
                added += add_to_rag(
                    text=text,
                    username=username,
                    source="medical_kb",
                    extra={"type": "json_kb"}
                )

        elif isinstance(kb_data, dict):
            for key, value in kb_data.items():
                text = f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}"
                added += add_to_rag(
                    text=text,
                    username=username,
                    source="medical_kb",
                    extra={"type": "json_kb", "section": key}
                )

        else:
            return {"status": "error", "message": "Unsupported JSON structure"}

        return {"status": "success", "chunks_added": added}

    except Exception as e:
        return {"status": "error", "message": str(e)}