from pathlib import Path
import chromadb

DB_DIR = Path("data/chroma")
DB_DIR.mkdir(parents=True, exist_ok=True)

_client = chromadb.PersistentClient(path=str(DB_DIR))
_collection = _client.get_or_create_collection(
    name="research_documents",
    metadata={"hnsw:space": "cosine"},
)

def get_collection():
    return _collection

def get_collection_stats():
    return _collection.count()
