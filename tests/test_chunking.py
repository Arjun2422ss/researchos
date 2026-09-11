from agents.graph import build_graph
from rag.ingestion import _chunk

def test_chunking():
    chunks = _chunk("hello " * 1000, size=100, overlap=10)
    assert len(chunks) > 1
    assert all(chunks)

def test_graph_builds():
    graph = build_graph()
    assert graph is not None
