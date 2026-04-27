import json
import hashlib
import numpy as np
from datetime import datetime, timezone
from redis import Redis
from typing import Any

from app.utils.config import config
from app.utils.logger import get_logger

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.85

CACHE_PREFIX = "nlsql:cache:"
VECTOR_PREFIX = "nlsql:vector:"
INDEX_KEY = "nlsql:cache:index"


def get_redis_client() -> Redis:
    """
    Creates a Redis client.
    decode_responses=False because we store raw bytes (vectors).
    """
    return Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        decode_responses=False  
    )


def _vector_to_bytes(vector: list[float]) -> bytes:
    """
    Converts a float list to bytes for Redis storage.
    numpy's tobytes() is the most efficient format.
    """
    return np.array(vector, dtype=np.float32).tobytes()


def _bytes_to_vector(data: bytes) -> np.ndarray:
    """Converts bytes back to numpy array."""
    return np.frombuffer(data, dtype=np.float32)


def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Computes cosine similarity between two vectors.

    Formula: cos(θ) = (A · B) / (|A| × |B|)
    
    Result range: -1 to 1
    - 1.0  = identical direction = same meaning
    - 0.0  = perpendicular = unrelated
    - -1.0 = opposite direction (rare in text embeddings)

    np.dot = dot product (A · B)
    np.linalg.norm = magnitude (|A|, |B|)
    """
    dot_product = np.dot(vec1, vec2)
    magnitude   = np.linalg.norm(vec1) * np.linalg.norm(vec2)

    if magnitude == 0:
        return 0.0

    return float(dot_product / magnitude)


# def _make_cache_key(question: str) -> str:
#     """
#     Creates a unique Redis key for a cache entry.
#     Uses MD5 hash of the question — short, unique, consistent.
    
#     WHY HASH THE QUESTION?
#     Redis keys should be short. A 200-char question as a key
#     wastes memory. MD5 gives a fixed 32-char key.
#     Collisions are astronomically unlikely for our use case.
#     """
#     question_hash = hashlib.md5(question.encode()).hexdigest()
#     # return f"{CACHE_PREFIX}{question_hash}"
#     return f"{CACHE_PREFIX}{role}:{user_id}:{question_hash}"

def _make_cache_key(question: str, user_id: int, role: str) -> str:
    """
    Creates a role-scoped cache key.

    WHY INCLUDE role + user_id?
    "show pending transactions" means different data for:
    - admin      → all transactions
    - supervisor → their team's transactions  
    - agent_dhoni → only dhoni's transactions

    Same question + different role = different SQL = different cache entry.
    Without this, admin's result leaks to agents. Critical security fix.

    Key format: nlsql:cache:{role}:{user_id}:{question_hash}
    """
    question_hash = hashlib.md5(question.encode()).hexdigest()
    return f"{CACHE_PREFIX}{role}:{user_id}:{question_hash}"


class SemanticCache:
    """
    Semantic cache that finds similar past questions
    using vector similarity instead of exact string matching.

    Usage:
        cache = SemanticCache()
        
        # Check cache before running pipeline
        hit = await cache.get(question, question_vector)
        if hit:
            return hit["result"]
        
        # Run pipeline
        result = await run_pipeline(question)
        
        # Store for future use
        await cache.set(question, question_vector, sql, result)
    """

    def __init__(self):
        self.client = get_redis_client()
        logger.info(
            "SemanticCache initialized | host=%s | port=%d | threshold=%.2f",
            config.REDIS_HOST, config.REDIS_PORT, SIMILARITY_THRESHOLD
        )

    def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error("Redis ping failed | error=%s", str(e))
            return False

    def get(
        self,
        question: str,
        question_vector: list[float],
        user_id: int,     
        role: str
    ) -> dict | None:
        """
        Looks for a semantically similar cached question.

        Algorithm:
        1. Get all cache entry keys from Redis index
        2. For each entry, load its stored vector
        3. Compute cosine similarity
        4. If similarity > threshold, return cached result

        Returns cached entry dict if hit, None if miss.

        WHY SCAN ALL ENTRIES?
        With 5 schema docs and typical usage, the cache
        will have at most a few hundred entries — scanning
        all of them takes microseconds.
        For millions of entries, you'd use a vector index
        (like Qdrant itself as a cache — advanced pattern).
        """
        try:
            cache_keys = self.client.lrange(INDEX_KEY, 0, -1)

            if not cache_keys:
                logger.info("Cache empty — miss")
                return None

            query_vec = np.array(question_vector, dtype=np.float32)
            best_similarity = 0.0
            best_entry = None

            for key_bytes in cache_keys:
                key = key_bytes.decode("utf-8")

                expected_prefix = f"{CACHE_PREFIX}{role}:{user_id}:"
                if not key.startswith(expected_prefix):
                    continue

                entry_bytes = self.client.get(key)
                if not entry_bytes:
                    continue  

                entry = json.loads(entry_bytes.decode("utf-8"))

                vector_key = key.replace(CACHE_PREFIX, VECTOR_PREFIX)
                vector_bytes = self.client.get(vector_key)
                if not vector_bytes:
                    continue

                cached_vec = _bytes_to_vector(vector_bytes)
                similarity = _cosine_similarity(query_vec, cached_vec)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_entry = entry

            if best_similarity >= SIMILARITY_THRESHOLD and best_entry:
                logger.info(
                    "Cache HIT |  role=%s | user_id=%d | similarity=%.4f | original_question='%s'",
                    best_similarity, role, user_id, 
                    best_entry.get("question", "")[:50]
                )
                best_entry["cache_similarity"] = best_similarity
                return best_entry

            logger.info(
                "Cache MISS | role=%s | user_id=%d | best_similarity=%.4f | threshold=%.2f",
                role, user_id, best_similarity, SIMILARITY_THRESHOLD
            )
            return None

        except Exception as e:
           
            logger.error("Cache get error — proceeding without cache | %s", str(e))
            return None

    def set(
        self,
        question:        str,
        question_vector: list[float],
        generated_sql:   str,
        result:          Any,
        row_count:       int = 0,
        user_id:         int = 0,
        role:            str = ""
    ) -> bool:
        """
        Stores a question + result in Redis cache.

        Stores TWO Redis keys per entry:
        1. CACHE_PREFIX + hash → JSON entry (question, sql, result)
        2. VECTOR_PREFIX + hash → raw vector bytes (for similarity search)

        Both expire at the same TTL.
        Also adds the cache key to our index list.
        """
        try:
            cache_key  = _make_cache_key(question , user_id, role)
            vector_key = cache_key.replace(CACHE_PREFIX, VECTOR_PREFIX)

            entry = {
                "question":     question,
                "generated_sql": generated_sql,
                "result":       result,
                "row_count":    row_count,
                "role":          role,     
                "user_id":       user_id,
                "cached_at":    datetime.now(timezone.utc).isoformat(),
            }

            ttl = config.REDIS_TTL_SECONDS

            self.client.setex(cache_key, ttl, json.dumps(entry, default=str))

            self.client.setex(vector_key, ttl,  _vector_to_bytes(question_vector) )

            self.client.lpush(INDEX_KEY, cache_key)

            logger.info(
                "Cache SET | role=%s | user_id=%d | question='%s' | TTL=%ds | sql_length=%d",
                role, user_id, question[:50], ttl, len(generated_sql)
            )
            return True

        except Exception as e:
            logger.error("Cache set error | %s", str(e))
            return False

    def clear(self) -> int:
        """
        Clears all cache entries.
        Useful for testing and manual cache invalidation.
        Returns number of keys deleted.
        """
        try:
            keys = self.client.keys(f"{CACHE_PREFIX}*")
            keys += self.client.keys(f"{VECTOR_PREFIX}*")
            keys += [INDEX_KEY.encode()]

            if keys:
                self.client.delete(*keys)

            logger.info("Cache cleared | %d keys deleted", len(keys))
            return len(keys)

        except Exception as e:
            logger.error("Cache clear error | %s", str(e))
            return 0

    def stats(self) -> dict:
        """
        Returns cache statistics.
        Used in the Streamlit dashboard to show cache performance.
        """
        try:
            cache_keys = self.client.lrange(INDEX_KEY, 0, -1)
            active_count = 0

            for key_bytes in cache_keys:
                key = key_bytes.decode("utf-8")
                if self.client.exists(key):
                    active_count += 1

            return {
                "total_entries":  len(cache_keys),
                "active_entries": active_count,
                "expired_entries": len(cache_keys) - active_count,
                "ttl_seconds":    config.REDIS_TTL_SECONDS,
                "threshold":      SIMILARITY_THRESHOLD
            }
        except Exception as e:
            logger.error("Cache stats error | %s", str(e))
            return {}


semantic_cache = SemanticCache()