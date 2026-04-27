from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, query
from app.db.connection import create_pool, close_pool
from app.graph.pipeline import build_pipeline
from app.utils.logger import get_logger
from app.cache.redis_cache import semantic_cache


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup sequence (order matters):
    1. PostgreSQL pool — needed by all DB operations
    2. Redis ping — verify cache is reachable
    3. Pipeline build — compiles LangGraph graph
       (done at import time in pipeline.py but we log it here)

    WHY VERIFY ON STARTUP?
    Better to fail fast at startup with a clear error
    than to fail silently on the first user request."""
    logger.info("=" * 55)
    logger.info("Starting NL-SQL RAG Pipeline API...")
    logger.info("=" * 55)
    
    await create_pool()
    logger.info("PostgreSQL pool ready")

    if semantic_cache.ping():
        logger.info("Redis cache ready")
    else:
        logger.warning("Redis not reachable — cache disabled")

    logger.info("LangGraph pipeline ready")

    logger.info("=" * 55)
    logger.info("All systems ready. API accepting requests.")
    logger.info("=" * 55)

    yield

    logger.info("Shutting down gracefully...")
    await close_pool()
    logger.info("Goodbye.")


app = FastAPI(
    title="NL-SQL RAG Pipeline",
    description="""
    Natural Language to SQL with Role-Based Access Control.
    
    Built with: LangGraph · FastAPI · Qdrant · Redis · PostgreSQL · GPT-4o-mini
    
    Roles:
    - **Admin**: Full access to all data
    - **Supervisor**: Access to their team's data only  
    - **Agent**: Access to their own transactions only
    """,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(query.router)



@app.get("/health", tags=["Health"])
async def health():
    """
    Health check — used by Docker, load balancers, monitoring.
    Returns cache status too so you can see if Redis is up.
    """
    cache_status = "healthy" if semantic_cache.ping() else "unreachable"
    return {
        "status":       "healthy",
        "service":      "nl-sql-rag-pipeline",
        "cache_status": cache_status,
        "version":      "1.0.0"
    }