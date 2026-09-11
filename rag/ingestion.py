from pathlib import Path
import hashlib
import re
from pypdf import PdfReader
from rag.store import get_collection

def _read_upload(upload):
    name = upload.name.lower()
    data = upload.getvalue()
    if name.endswith(".pdf"):
        import io
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="ignore")

def _chunk(text, size=1200, overlap=200):
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
    return chunks

def ingest_files(uploads):
    collection = get_collection()
    total = 0
    for upload in uploads:
        text = _read_upload(upload)
        chunks = _chunk(text)
        ids, docs, metas = [], [], []
        file_hash = hashlib.sha1(upload.getvalue()).hexdigest()[:12]
        for i, chunk in enumerate(chunks):
            ids.append(f"{file_hash}-{i}")
            docs.append(chunk)
            metas.append({"source": upload.name, "chunk": i})
        if ids:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)
            total += len(ids)
    return {"files": len(uploads), "chunks": total}
