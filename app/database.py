import asyncio
import asyncpg

from app.config import settings
import logging
logger = logging.getLogger(__name__)
_pool: asyncpg.Pool | None = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


async def init_db() -> None:
    global _pool
    max_retries = 10
    retry_delay = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to database (attempt {attempt}/{max_retries})")
            _pool = await asyncpg.create_pool(settings.DATABASE_URL)
            break
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            if attempt == max_retries:
                raise RuntimeError(f"Could not connect to database after {max_retries} attempts")
            await asyncio.sleep(retry_delay)


    dims = settings.EMBEDDING_DIMENSIONS

    async with _pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS student_embeddings (
                user_id UUID PRIMARY KEY,
                embedding vector({dims}) NOT NULL,
                cv_text TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS subject_embeddings (
                subject_id UUID PRIMARY KEY,
                embedding vector({dims}) NOT NULL,
                subject_text TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS rag_chunks (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_name TEXT NOT NULL,
                document_type TEXT NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding vector({dims}) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_student_embeddings_hnsw
                ON student_embeddings USING hnsw (embedding vector_cosine_ops)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subject_embeddings_hnsw
                ON subject_embeddings USING hnsw (embedding vector_cosine_ops)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_chunks_hnsw
                ON rag_chunks USING hnsw (embedding vector_cosine_ops)
            """
        )


async def close_db() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None
