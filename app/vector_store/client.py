from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, VectorParams, PointStruct)
from app.utils.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Returns singleton Qdrant client."""
    global qdrant_client
    if qdrant_client is None:
        qdrant_client = QdrantClient(
            host=config.QDRANT_HOST,
            port=config.QDRANT_PORT
        )
        logger.info(
            "Qdrant client created | host=%s | port=%d",
            config.QDRANT_HOST, config.QDRANT_PORT
        )
    return qdrant_client


def create_collection_if_not_exists(client: QdrantClient) -> None:
   
    collections = client.get_collections().collections
    existing = [c.name for c in collections]

    if config.QDRANT_COLLECTION_NAME in existing:
        logger.info(
            "Collection already exists | name=%s",
            config.QDRANT_COLLECTION_NAME
        )
        return

    client.create_collection(
        collection_name=config.QDRANT_COLLECTION_NAME,
        vectors_config=VectorParams(
            size=1536,          # text-embedding-3-small dimensions
            distance=Distance.COSINE
        )
    )
    logger.info(
        "Collection created | name=%s | dimensions=1536 | distance=COSINE",
        config.QDRANT_COLLECTION_NAME
    )