import logging
from app.database import get_pool

logger = logging.getLogger(__name__)

STOPWORDS = {
    'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en', 'au',
    'aux', 'est', 'the', 'a', 'an', 'of', 'in', 'and', 'or', 'to', 'for',
    'with', 'on', 'at', 'is', 'are', 'was', 'be', 'by', 'this', 'that',
    'it', 'its', 'not', 'but', 'from', 'as', 'we', 'ce', 'qui', 'que',
    'dans', 'sur', 'par', 'pour', 'avec', 'son', 'sa', 'se', 'si', 'ou',
    'ni', 'car', 'je', 'tu', 'il', 'nous', 'vous', 'ils', 'elle', 'mon',
    'ton', 'leur', 'mes', 'tes', 'ses', 'nos', 'vos', 'leurs',
}


class NoEmbeddingError(Exception):
    pass


def extract_keywords(cv_text: str, subject_text: str, top_n: int = 5) -> list[str]:
    def tokenize(text: str) -> list[str]:
        return [
            w.lower().strip('.,;:!?()[]{}"\'-')
            for w in text.split()
            if len(w) > 2
        ]

    cv_words = set(tokenize(cv_text)) - STOPWORDS
    subject_words = tokenize(subject_text)

    freq: dict[str, int] = {}
    for word in subject_words:
        if word in cv_words and word not in STOPWORDS:
            freq[word] = freq.get(word, 0) + 1

    sorted_keywords = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_keywords[:top_n]]


async def get_suggestions(user_id: str) -> list[dict]:
    pool = get_pool()

    async with pool.acquire() as conn:
        student_row = await conn.fetchrow(
            "SELECT embedding, cv_text FROM student_embeddings WHERE user_id = $1",
            user_id,
        )

    if not student_row:
        raise NoEmbeddingError(f"No embedding found for user {user_id}")

    student_embedding = student_row["embedding"]
    cv_text = student_row["cv_text"]

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT subject_id,
                   subject_text,
                   1 - (embedding <=> $1::vector) AS score
            FROM subject_embeddings
            ORDER BY embedding <=> $1::vector
            LIMIT 5
            """,
            str(student_embedding),
        )

    results = []
    for row in rows:
        keywords = extract_keywords(cv_text, row["subject_text"])
        results.append({
            "subjectId": str(row["subject_id"]),
            "score": round(float(row["score"]), 4),
            "matchedKeywords": keywords,
        })

    return results
