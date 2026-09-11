from rag.store import get_collection

def retrieve(query, top_k=5):
    collection = get_collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
    )
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return [
        {
            "text": doc,
            "source": meta.get("source", "Unknown"),
            "chunk": meta.get("chunk", ""),
            "distance": distances[i] if i < len(distances) else None,
        }
        for i, (doc, meta) in enumerate(zip(docs, metas))
    ]
