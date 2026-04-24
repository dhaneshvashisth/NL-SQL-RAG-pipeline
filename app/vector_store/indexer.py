import asyncio
from qdrant_client.models import PointStruct
from app.utils.config import config


from app.vector_store.client import get_qdrant_client, create_collection_if_not_exists
from app.vector_store.embedder import embed_batch
from app.vector_store.schema_docs import SCHEMA_DOCUMENTS
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def index_schema_documents() -> None:
    """
    Main indexing function:
    1. Connect to Qdrant
    2. Create collection if needed
    3. Embed all schema documents in one batch API call
    4. Upsert all points into Qdrant

    WHY UPSERT NOT INSERT?
    Upsert = insert if not exists, update if exists.
    Safe to run multiple times without duplicates.
    If you update a schema description, re-running this
    will update the existing vectors automatically.
    """
    logger.info("Starting schema indexing into Qdrant...")

    client = get_qdrant_client()
    create_collection_if_not_exists(client)

    texts = [doc["content"] for doc in SCHEMA_DOCUMENTS]
    logger.info("Embedding %d schema documents...", len(texts))

    vectors = await embed_batch(texts)
    logger.info("Embeddings received | count=%d", len(vectors))

    points = []
    for i, (doc, vector) in enumerate(zip(SCHEMA_DOCUMENTS, vectors)):
        point = PointStruct(
            id=i + 1, 
            vector=vector,
            payload={
                "doc_id":        doc["doc_id"],
                "table_name":    doc["table_name"],
                "content":       doc["content"],
                "sql_reference": doc["sql_reference"]
            }
        )
        points.append(point)
        logger.info(
            "Point prepared | id=%d | doc=%s",
            i + 1, doc["doc_id"]
        )

    client.upsert(
        collection_name=config.QDRANT_COLLECTION_NAME,
        points=points
    )

    logger.info(
        "Schema indexing complete | %d documents stored in Qdrant",
        len(points)
    )


async def retrieve_relevant_schemas( query: str, top_k: int = 3) -> list[dict]:
    """  THE RAG RETRIEVAL STEP.
    Given a user's natural language question:
    1. Embed the question
    2. Search Qdrant for most similar schema documents
    3. Return those documents as context for SQL generation

    top_k=3 means: return 3 most relevant schema docs.
    We don't need all 5 — just the most relevant ones.
    Smaller context = cheaper + more accurate LLM output.

    WHY NOT JUST SEND ALL SCHEMAS?
    With 5 tables it seems fine. But in real systems with
    50-100 tables, sending all schemas would:
    - Cost 10x more per query
    - Confuse the LLM with irrelevant tables
    - Increase hallucination risk
    RAG solves this at scale.
    """
    from app.vector_store.embedder import embed_text
    from app.utils.config import config

    logger.info(
        "Retrieving relevant schemas | query='%s' | top_k=%d",
        query[:50], top_k
    )

    query_vector = await embed_text(query)

    client = get_qdrant_client()
    results = client.search(
        collection_name=config.QDRANT_COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True  
    )

    retrieved = []
    for result in results:
        retrieved.append({
            "doc_id":        result.payload["doc_id"],
            "table_name":    result.payload["table_name"],
            "content":       result.payload["content"],
            "sql_reference": result.payload["sql_reference"],
            "score":         result.score   
        })
        logger.info(
            "Retrieved | doc=%s | similarity=%.4f",
            result.payload["doc_id"], result.score
        )

    return retrieved


if __name__ == "__main__":
    asyncio.run(index_schema_documents())