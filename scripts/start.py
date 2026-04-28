import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from app.utils.logger import get_logger
logger = get_logger(__name__)


def wait_for_postgres(max_retries: int = 30) -> bool:
    """
    Waits for PostgreSQL to be ready.
    Tries every 2 seconds up to max_retries times.
    """
    import psycopg2
    from app.utils.config import config

    logger.info("Waiting for PostgreSQL to be ready...")

    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=config.POSTGRES_HOST,
                port=config.POSTGRES_PORT,
                user=config.POSTGRES_USER,
                password=config.POSTGRES_PASSWORD,
                dbname=config.POSTGRES_DB
            )
            conn.close()
            logger.info("PostgreSQL is ready!")
            return True
        except Exception:
            logger.info(
                "PostgreSQL not ready yet... attempt %d/%d",
                attempt + 1, max_retries
            )
            time.sleep(2)

    logger.error("PostgreSQL did not become ready in time.")
    return False


def check_tables_exist() -> bool:
    """Check if tables already exist (skip seeding if yes)."""
    import psycopg2
    from app.utils.config import config

    try:
        conn = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD,
            dbname=config.POSTGRES_DB
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        exists = cur.fetchone()[0]
        conn.close()
        return exists
    except Exception:
        return False


def check_qdrant_indexed() -> bool:
    """Check if Qdrant collection has documents."""
    try:
        from qdrant_client import QdrantClient
        from app.utils.config import config

        client = QdrantClient(
            host=config.QDRANT_HOST,
            port=config.QDRANT_PORT
        )
        collections = client.get_collections().collections
        names = [c.name for c in collections]

        if config.QDRANT_COLLECTION_NAME not in names:
            return False

        info = client.get_collection(config.QDRANT_COLLECTION_NAME)
        return info.points_count > 0
    except Exception:
        return False


async def run_startup():
    """Full startup sequence."""
    logger.info("=" * 60)
    logger.info("NL-SQL RAG Pipeline — Startup Sequence")
    logger.info("=" * 60)

    if not wait_for_postgres():
        logger.error("Cannot connect to PostgreSQL. Is Docker running?")
        sys.exit(1)

    if not check_tables_exist():
        logger.info("Fresh database detected — running seed...")
        from app.db.seed import run_seed
        run_seed()
        logger.info("Database seeded successfully.")
    else:
        logger.info("Database already seeded — skipping.")

    if not check_qdrant_indexed():
        logger.info("Qdrant empty — indexing schema documents...")
        from app.vector_store.indexer import index_schema_documents
        await index_schema_documents()
        logger.info("Schema indexed into Qdrant successfully.")
    else:
        logger.info("Qdrant already indexed — skipping.")

    logger.info("=" * 60)
    logger.info("All systems ready!")
    logger.info("API:       http://localhost:8000")
    logger.info("API Docs:  http://localhost:8000/docs")
    logger.info("Frontend:  http://localhost:8501")
    logger.info("Qdrant UI: http://localhost:6333/dashboard")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_startup())