import json

from backend.db.database import get_connection, init_db
from backend.services.vector_retrieval_service import VectorRetrievalService
from backend.services.qdrant_vector_store import get_qdrant_vector_store


if __name__ == "__main__":
    init_db()
    with get_connection() as conn:
        documents = [dict(row) for row in conn.execute("SELECT id, title, content FROM documents WHERE content != ''")]
    service = VectorRetrievalService()
    get_qdrant_vector_store().reset()
    result = []
    for document in documents:
        result.append({"id": document["id"], "title": document["title"],
                       "chunks": service.index_document(document["id"], document["content"])})
    print(json.dumps(result, ensure_ascii=False, indent=2))
