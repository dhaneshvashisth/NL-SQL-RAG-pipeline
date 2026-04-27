import asyncio
import pytest
from app.cache.redis_cache import SemanticCache, _cosine_similarity
import numpy as np


def test_redis_connection():
    """Redis must be reachable before any other test."""
    cache = SemanticCache()
    assert cache.ping() is True


def test_cosine_similarity_identical():
    """Identical vectors should have similarity = 1.0"""
    vec = [0.1, 0.2, 0.3, 0.4]
    sim = _cosine_similarity(np.array(vec), np.array(vec))
    assert abs(sim - 1.0) < 0.0001


def test_cosine_similarity_orthogonal():
    """Perpendicular vectors should have similarity = 0.0"""
    vec1 = [1.0, 0.0]
    vec2 = [0.0, 1.0]
    sim = _cosine_similarity(np.array(vec1), np.array(vec2))
    assert abs(sim - 0.0) < 0.0001


def test_cache_set_and_get():
    """Exact same vector should always return a cache hit."""
    cache = SemanticCache()
    cache.clear()

    fake_vector = [0.1] * 1536

    cache.set(
        question="test question",
        question_vector=fake_vector,
        generated_sql="SELECT 1",
        result=[],
        row_count=0
    )

    hit = cache.get("test question", fake_vector)
    assert hit is not None
    assert hit["question"] == "test question"
    assert hit["generated_sql"] == "SELECT 1"


def test_cache_miss_on_different_question():
    """Very different vectors should not match."""
    cache = SemanticCache()
    cache.clear()

    vec1 = [1.0] + [0.0] * 1535
    cache.set("question A", vec1, "SELECT 1", [], 0)

    vec2 = [0.0, 1.0] + [0.0] * 1534
    hit = cache.get("question B", vec2)
    assert hit is None


def test_cache_stats():
    """Stats should reflect stored entries."""
    cache = SemanticCache()
    cache.clear()

    fake_vector = [0.5] * 1536
    cache.set("stats test", fake_vector, "SELECT 1", [], 0)

    stats = cache.stats()
    assert stats["active_entries"] >= 1