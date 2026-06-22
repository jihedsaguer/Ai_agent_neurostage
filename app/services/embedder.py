import asyncio
import logging
from datetime import datetime
from openai import AsyncOpenAI, RateLimitError, APIError
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def get_llm_client() -> AsyncOpenAI:
    if settings.LLM_PROVIDER == "ollama":
        return AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key="ollama",
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def embed_text(text: str) -> list[float]:
    client = get_llm_client()
    last_error = None

    for attempt in range(3):
        try:
            response = await client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=text,
            )
            return response.data[0].embedding
        except RateLimitError as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(f"Rate limit hit, retrying in {wait}s (attempt {attempt + 1})")
            await asyncio.sleep(wait)
        except APIError as e:
            last_error = e
            wait = 2 ** attempt
            logger.error(f"API error: {e}, retrying in {wait}s (attempt {attempt + 1})")
            await asyncio.sleep(wait)

    raise RuntimeError(f"embedding_failed after 3 attempts: {last_error}")


async def notify_nestjs(user_id: str) -> None:
    url = f"{settings.NESTJS_INTERNAL_URL}/internal/profiles/{user_id}/ai-processed"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                url,
                headers={"X-Internal-Secret": settings.INTERNAL_SECRET},
            )
            if response.status_code != 200:
                logger.warning(
                    f"NestJS callback returned {response.status_code} for user {user_id}"
                )
            else:
                logger.info(f"NestJS notified successfully for user {user_id}")
    except Exception as e:
        logger.warning(f"NestJS callback failed for user {user_id}: {e}")


async def embed_and_store_student(
    pool,
    user_id: str,
    extracted_text: str,
    skills: list[str],
    university: str,
    specialization: str,
    level: str,
) -> None:
    input_text = (
        f"{extracted_text}\n"
        f"skills: {', '.join(skills)}\n"
        f"university: {university}\n"
        f"specialization: {specialization}\n"
        f"level: {level}"
    )

    vector = await embed_text(input_text)
    now = datetime.utcnow()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO student_embeddings (user_id, embedding, cv_text, updated_at)
            VALUES ($1, $2::vector, $3, $4)
            ON CONFLICT (user_id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    cv_text = EXCLUDED.cv_text,
                    updated_at = EXCLUDED.updated_at
            """,
            user_id,
            str(vector),
            extracted_text,
            now,
        )

    logger.info(f"Student embedding stored for user {user_id}")
    asyncio.create_task(notify_nestjs(user_id))


async def embed_and_store_subject(
    pool,
    subject_id: str,
    titre: str,
    description: str,
    techno: list[str],
    prerequis: str,
    niveau: str,
) -> None:
    input_text = (
        f"{titre}\n"
        f"{description}\n"
        f"technologies: {', '.join(techno)}\n"
        f"prerequisites: {prerequis}\n"
        f"level: {niveau}"
    )

    vector = await embed_text(input_text)
    now = datetime.utcnow()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO subject_embeddings (subject_id, embedding, subject_text, updated_at)
            VALUES ($1, $2::vector, $3, $4)
            ON CONFLICT (subject_id) DO UPDATE
                SET embedding = EXCLUDED.embedding,
                    subject_text = EXCLUDED.subject_text,
                    updated_at = EXCLUDED.updated_at
            """,
            subject_id,
            str(vector),
            input_text,
            now,
        )

    logger.info(f"Subject embedding stored for subject {subject_id}")