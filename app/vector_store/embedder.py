

from openai import AsyncOpenAI
from app.utils.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)


openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


async def embed_text(text: str) -> list[float]:

    text = text.strip().replace("\n", " ")

    logger.info(
        "Embedding text | model=%s | length=%d chars",
        EMBEDDING_MODEL, len(text)
    )

    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )

    vector = response.data[0].embedding

    logger.info(
        "Embedding complete | dimensions=%d",
        len(vector)
    )
    return vector


async def embed_batch(texts: list[str]) -> list[list[float]]:

    cleaned = [t.strip().replace("\n", " ") for t in texts]

    logger.info(
        "Batch embedding | count=%d | model=%s",
        len(cleaned), EMBEDDING_MODEL
    )

    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned
    )

    vectors = [item.embedding for item in response.data]

    logger.info("Batch embedding complete | vectors=%d", len(vectors))
    return vectors