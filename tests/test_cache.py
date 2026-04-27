# import asyncio
# import pytest
# from app.cache.redis_cache import SemanticCache, _cosine_similarity
# import numpy as np


# def test_redis_connection():
#     """Redis must be reachable before any other test."""
#     cache = SemanticCache()
#     assert cache.ping() is True


# def test_cosine_similarity_identical():
#     """Identical vectors should have similarity = 1.0"""
#     vec = [0.1, 0.2, 0.3, 0.4]
#     sim = _cosine_similarity(np.array(vec), np.array(vec))
#     assert abs(sim - 1.0) < 0.0001


# def test_cosine_similarity_orthogonal():
#     """Perpendicular vectors should have similarity = 0.0"""
#     vec1 = [1.0, 0.0]
#     vec2 = [0.0, 1.0]
#     sim = _cosine_similarity(np.array(vec1), np.array(vec2))
#     assert abs(sim - 0.0) < 0.0001


# def test_cache_set_and_get():
#     """Exact same vector should always return a cache hit."""
#     cache = SemanticCache()
#     cache.clear()

#     fake_vector = [0.1] * 1536

#     cache.set(
#         question="test question",
#         question_vector=fake_vector,
#         generated_sql="SELECT 1",
#         result=[],
#         row_count=0
#     )

#     hit = cache.get("test question", fake_vector)
#     assert hit is not None
#     assert hit["question"] == "test question"
#     assert hit["generated_sql"] == "SELECT 1"


# def test_cache_miss_on_different_question():
#     """Very different vectors should not match."""
#     cache = SemanticCache()
#     cache.clear()

#     vec1 = [1.0] + [0.0] * 1535
#     cache.set("question A", vec1, "SELECT 1", [], 0)

#     vec2 = [0.0, 1.0] + [0.0] * 1534
#     hit = cache.get("question B", vec2)
#     assert hit is None


# def test_cache_stats():
#     """Stats should reflect stored entries."""
#     cache = SemanticCache()
#     cache.clear()

#     fake_vector = [0.5] * 1536
#     cache.set("stats test", fake_vector, "SELECT 1", [], 0)

#     stats = cache.stats()
#     assert stats["active_entries"] >= 1



"""
test_cache.py — Redis semantic cache tests
"""

import pytest
import numpy as np
from app.cache.redis_cache import (
    SemanticCache,
    _cosine_similarity,
    SIMILARITY_THRESHOLD
)


def test_redis_connection():
    """Redis must be reachable."""
    cache = SemanticCache()
    assert cache.ping() is True


def test_cosine_similarity_identical_vectors():
    """Identical vectors = similarity 1.0."""
    vec = [0.1, 0.2, 0.3, 0.4, 0.5]
    sim = _cosine_similarity(np.array(vec), np.array(vec))
    assert abs(sim - 1.0) < 0.0001


def test_cosine_similarity_orthogonal_vectors():
    """Perpendicular vectors = similarity 0.0."""
    sim = _cosine_similarity(
        np.array([1.0, 0.0]),
        np.array([0.0, 1.0])
    )
    assert abs(sim - 0.0) < 0.0001


def test_cosine_similarity_range():
    """Similarity must always be between -1 and 1."""
    import random
    for _ in range(10):
        v1 = np.array([random.uniform(-1, 1) for _ in range(100)])
        v2 = np.array([random.uniform(-1, 1) for _ in range(100)])
        sim = _cosine_similarity(v1, v2)
        assert -1.0 <= sim <= 1.0


def test_cache_set_and_get_exact(clear_cache):
    """Exact same vector must always return cache hit."""
    cache = SemanticCache()
    vec = [0.42] * 1536

    cache.set(
        question="show pending transactions",
        question_vector=vec,
        generated_sql="SELECT * FROM transactions WHERE status='pending'",
        result="3 pending transactions found",
        row_count=3,
        user_id=1,
        role="admin"
    )

    hit = cache.get("show pending transactions", vec, user_id=1, role="admin")

    assert hit is not None
    assert hit["question"] == "show pending transactions"
    assert hit["row_count"] == 3
    assert hit["cache_similarity"] >= SIMILARITY_THRESHOLD


def test_cache_miss_unrelated_question(clear_cache):
    """Unrelated question must always miss."""
    cache = SemanticCache()

    # Store with one vector direction
    vec1 = [1.0] + [0.0] * 1535
    cache.set("pending transactions", vec1, "SELECT 1", "result", 1,
              user_id=1, role="admin")

    # Query with orthogonal vector
    vec2 = [0.0, 1.0] + [0.0] * 1534
    hit = cache.get("platform revenue", vec2, user_id=1, role="admin")

    assert hit is None


def test_cache_role_isolation(clear_cache):
    """Admin cache must not be accessible by agent."""
    cache = SemanticCache()
    vec = [0.5] * 1536

    cache.set("show transactions", vec, "SELECT * FROM transactions",
              "All 479 transactions", 479, user_id=1, role="admin")

    hit = cache.get("show transactions", vec, user_id=4, role="agent")
    assert hit is None


def test_cache_user_isolation(clear_cache):
    """Different users with same role must not share cache."""
    cache = SemanticCache()
    vec = [0.6] * 1536

    cache.set("my transactions", vec, "SELECT * WHERE agent_id=4",
              "55 transactions", 55, user_id=4, role="agent")

    hit = cache.get("my transactions", vec, user_id=5, role="agent")
    assert hit is None


def test_cache_stats_reflect_entries(clear_cache):
    """Stats must show correct entry count."""
    cache = SemanticCache()
    vec = [0.1] * 1536

    cache.set("test question", vec, "SELECT 1", "result", 0,
              user_id=1, role="admin")

    stats = cache.stats()
    assert stats["active_entries"] >= 1
    assert stats["ttl_seconds"] > 0


def test_cache_clear_removes_all(clear_cache):
    """Clear must remove all entries."""
    cache = SemanticCache()
    vec = [0.2] * 1536

    cache.set("q1", vec, "SQL1", "r1", 0, user_id=1, role="admin")
    cache.set("q2", vec, "SQL2", "r2", 0, user_id=2, role="supervisor")

    deleted = cache.clear()
    assert deleted > 0

    hit = cache.get("q1", vec, user_id=1, role="admin")
    assert hit is None