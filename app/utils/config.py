import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    """Centralized configuration class. All settings are read from environment variables. """

    POSTGRES_USER: str     = os.getenv("POSTGRES_USER", "nlsql_user")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str       = os.getenv("POSTGRES_DB", "nlsql_db")
    POSTGRES_HOST: str     = os.getenv("POSTGRES_HOST", "127.0.0.1")
    POSTGRES_PORT: int     = int(os.getenv("POSTGRES_PORT", "5432"))

    QDRANT_HOST: str            = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int            = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "schema_embeddings")

    REDIS_HOST: str      = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int      = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_TTL_SECONDS: int = int(os.getenv("REDIS_TTL_SECONDS", "3600"))

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    JWT_SECRET_KEY: str    = os.getenv("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str     = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))

    APP_ENV: str   = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def POSTGRES_DSN(self) -> str:
        """
        Built at ACCESS time using @property, not at class definition.
        which guarantees real .env values are always used. """
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


config = Config()