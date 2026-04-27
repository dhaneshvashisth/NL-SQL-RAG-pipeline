import asyncio
from app.cache.redis_cache import semantic_cache
from app.vector_store.embedder import embed_text

async def test():
    print("Redis ping:", semantic_cache.ping())

    vec = await embed_text("show me all pending transactions")
    semantic_cache.set(
        question="show me all pending transactions",
        question_vector=vec,
        generated_sql="SELECT * FROM transactions WHERE status = 'pending'",
        result=[{"id": 1, "status": "pending", "amount": 500.00}],
        row_count=1
    )
    print("Cache SET done")

    vec2 = await embed_text("show pending transactions")
    hit = semantic_cache.get("show pending transactions", vec2)
    if hit:
        print(f"Cache HIT | similarity={hit['cache_similarity']:.4f}")
        print(f"Original question: {hit['question']}")
    else:
        print("Cache MISS — threshold might need tuning")

    vec3 = await embed_text("who is the top performing agent this month")
    miss = semantic_cache.get("who is the top performing agent this month", vec3)
    print(f"Different question result: {'HIT' if miss else 'MISS (expected)'}")

    print("Cache stats:", semantic_cache.stats())

asyncio.run(test())