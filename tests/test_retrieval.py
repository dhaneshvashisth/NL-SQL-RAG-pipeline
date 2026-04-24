import asyncio
from app.vector_store.indexer import retrieve_relevant_schemas

async def test():
    queries = [
        "show me pending transactions for agent dhoni",
        "how many agents does supervisor virat have",
        "compare platform performance this month"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        print("-" * 50)
        results = await retrieve_relevant_schemas(query)
        for r in results:
            print(f"  doc={r['doc_id']} | score={r['score']:.4f}")

asyncio.run(test())