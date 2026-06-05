import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Create a global connection pool (singleton)
_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    return _pool

async def upsert_embedding(emp_id: str, embedding: bytes):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO employee_embeddings (emp_id, embedding)
            VALUES ($1, $2)
            ON CONFLICT (emp_id) DO UPDATE SET embedding = EXCLUDED.embedding
            """,
            emp_id,
            embedding,
        )

async def fetch_all_embeddings():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT emp_id, embedding FROM employee_embeddings")
        return [(row["emp_id"], row["embedding"]) for row in rows]
