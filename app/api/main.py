


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.db.connection import create_pool, close_pool
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("Starting my NL-SQL RAG Pipeline API...")
    await create_pool()
    logger.info("Application started succesfully.")

    yield  
    logger.info("Shutting down...")
    await close_pool()
    logger.info("Goodbye!")


app = FastAPI(
    title="NL-SQL RAG Pipeline",
    description="Natural Language to SQL with Role-Based Access Control",
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


@app.get("/health")
async def health():

    return {"status": "healthy", "service": "nl-sql-rag-pipeline"}