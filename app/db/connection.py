
import asyncpg
from asyncpg import Pool
from app.utils.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

_pool: Pool | None = None


async def create_pool() -> Pool:
    """Creates the asyncpg connection pool.
    Called ONCE when FastAPI app starts up.    
    min_size=5  → always keep 5 connections open (ready to use)
    max_size=20 → never open more than 20 simultaneous connections"""
    global _pool

    logger.info("Creating asyncpg connection pool...")

    _pool = await asyncpg.create_pool(
        dsn=config.POSTGRES_DSN,
        min_size=5,
        max_size=20,
        command_timeout=60,       
        statement_cache_size=100,
    )

    logger.info(
        "Connection pool created | min=%d max=%d", 5, 20
    )
    return _pool


async def get_pool() -> Pool:
    """Returns the existing pool. will be Used as a FastAPI dependency. """

    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. "
            "Call create_pool() during app startup."
        )
    return _pool


async def close_pool() -> None:
    """ closes all connections in the pool. Called when FastAPI app shuts down. """
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Connection pool closed gracefully.")
        _pool = None