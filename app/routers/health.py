import shutil

from fastapi import APIRouter

from app.config import settings
from app.database import get_pool

router = APIRouter()


@router.get("/health")
async def health_check():
    pgvector_ok = False
    tesseract_ok = shutil.which("tesseract") is not None

    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            pgvector_ok = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            )
    except Exception:
        pgvector_ok = False

    llm_ok = settings.LLM_PROVIDER == "ollama" or bool(settings.OPENAI_API_KEY)
    checks_ok = pgvector_ok and tesseract_ok and llm_ok

    return {
        "status": "ok" if checks_ok else "degraded",
        "llm_provider": settings.LLM_PROVIDER,
        "pgvector": pgvector_ok,
        "tesseract": tesseract_ok,
    }
