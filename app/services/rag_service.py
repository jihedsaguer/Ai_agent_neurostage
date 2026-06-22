import logging
import re
from datetime import datetime
from openai import AsyncOpenAI, APIError
from app.config import settings
from app.database import get_pool
from app.services.extractor import extract_text
from app.services.embedder import embed_text

logger = logging.getLogger(__name__)

NO_ANSWER_RESPONSE = {
    "answer": "Je ne dispose pas d'informations suffisantes pour répondre à cette question.",
    "sources": [],
}

SIMILARITY_THRESHOLD = 0.5


def get_llm_client() -> AsyncOpenAI:
    if settings.LLM_PROVIDER == "ollama":
        return AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key="ollama",
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks using a simple sliding window."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk = text[start:end].strip()
        if len(chunk) > 50:  # skip tiny chunks
            chunks.append(chunk)
        if end == text_length:
            break
        start = end - overlap  # overlap with previous chunk

    return chunks


async def ingest_document(
    file_path: str,
    document_name: str,
    document_type: str,
) -> int:
    """Extract text from a document, chunk it, embed each chunk, store in rag_chunks."""

    # extract text using existing extractor
    try:
        # detect file type from extension
        file_path_lower = file_path.lower()
        if file_path_lower.endswith(".pdf"):
            file_type = "application/pdf"
        elif file_path_lower.endswith(".docx"):
            file_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif file_path_lower.endswith((".jpg", ".jpeg")):
            file_type = "image/jpeg"
        elif file_path_lower.endswith(".png"):
            file_type = "image/png"
        else:
            file_type = "application/pdf"  # default

        result = extract_text(file_path, file_type)
        text = result["text"]
    except FileNotFoundError:
        raise
    except ValueError as e:
        raise ValueError(f"Could not extract text from document: {e}")

    # split into chunks
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No usable chunks extracted from document")

    logger.info(f"Ingesting '{document_name}': {len(chunks)} chunks")

    pool = get_pool()
    stored = 0

    for index, chunk in enumerate(chunks):
        try:
            vector = await embed_text(chunk)
            now = datetime.utcnow()

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO rag_chunks
                        (document_name, document_type, chunk_text, chunk_index, embedding, created_at)
                    VALUES ($1, $2, $3, $4, $5::vector, $6)
                    """,
                    document_name,
                    document_type,
                    chunk,
                    index,
                    str(vector),
                    now,
                )
            stored += 1
        except Exception as e:
            logger.error(f"Failed to embed chunk {index} of '{document_name}': {e}")

    logger.info(f"Stored {stored}/{len(chunks)} chunks for '{document_name}'")
    return stored


async def answer_question(question: str, user_id: str) -> dict:
    """Embed the question, retrieve relevant chunks, generate a cited answer."""

    # embed the question
    try:
        question_vector = await embed_text(question)
    except RuntimeError as e:
        raise RuntimeError(f"Failed to embed question: {e}")

    pool = get_pool()

    # retrieve top 5 most similar chunks
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                document_name,
                chunk_text,
                1 - (embedding <=> $1::vector) AS score
            FROM rag_chunks
            ORDER BY embedding <=> $1::vector
            LIMIT 5
            """,
            str(question_vector),
        )

    # filter by similarity threshold
    relevant = [
        row for row in rows
        if float(row["score"]) >= SIMILARITY_THRESHOLD
    ]

    if not relevant:
        logger.info(f"No relevant chunks found for question from user {user_id}")
        return NO_ANSWER_RESPONSE

    # build context from chunks
    context_parts = []
    for i, row in enumerate(relevant, 1):
        context_parts.append(
            f"[Source {i}: {row['document_name']}]\n{row['chunk_text']}"
        )
    context = "\n\n".join(context_parts)

    system_prompt = """You are a helpful assistant for SOTETEL's internship management platform.
Answer questions about internship procedures, conventions, and regulations using ONLY the provided context.
Always cite the document name when you use information from it.
If the context does not contain enough information to answer, say so clearly.
Respond in the same language as the question."""

    user_prompt = f"Context:\n{context}\n\nQuestion: {question}"

    client = get_llm_client()

    try:
        response = await client.chat.completions.create(
            model=settings.GENERATION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # lower temperature for factual answers
        )
        answer = response.choices[0].message.content.strip()
    except APIError as e:
        logger.error(f"LLM API error during RAG query: {e}")
        raise RuntimeError(f"generation_failed: {e}")

    # build sources list — deduplicate by document name
    seen = set()
    sources = []
    for row in relevant:
        doc_name = row["document_name"]
        if doc_name not in seen:
            seen.add(doc_name)
            sources.append({
                "documentName": doc_name,
                "excerpt": row["chunk_text"][:200] + "..." if len(row["chunk_text"]) > 200 else row["chunk_text"],
            })

    return {
        "answer": answer,
        "sources": sources,
    }
