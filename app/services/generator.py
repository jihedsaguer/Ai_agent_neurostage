import json
import logging
from openai import AsyncOpenAI, APIError
from app.config import settings
from app.database import get_pool

logger = logging.getLogger(__name__)


class StudentNotFoundError(Exception):
    pass


class GenerationError(Exception):
    pass


def get_llm_client() -> AsyncOpenAI:
    if settings.LLM_PROVIDER == "ollama":
        return AsyncOpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key="ollama",
        )
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_subject_draft(
    student_ids: list[str],
    encadreur_id: str,
    context: str | None,
) -> dict:
    pool = get_pool()

    # fetch cv_text for all students in one query
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, cv_text FROM student_embeddings WHERE user_id = ANY($1::uuid[])",
            student_ids,
        )

    found_ids = {str(row["user_id"]) for row in rows}
    missing = [sid for sid in student_ids if sid not in found_ids]
    if missing:
        raise StudentNotFoundError(
            f"No embedding found for student(s): {', '.join(missing)}"
        )

    combined_cv = "\n---\n".join(row["cv_text"] for row in rows)

    system_prompt = """You are an expert at creating internship subjects for a Tunisian telecom company called SOTETEL.
Analyze the provided student CV(s) and generate one internship subject that matches their skills and level.
Respond only in valid JSON with exactly these fields and no other text:
{
  "titre": "subject title in French",
  "description": "2-3 sentence description in French",
  "techno": ["tech1", "tech2", "tech3"],
  "prerequis": "prerequisites in French",
  "niveau": "one of: L1, L2, L3, M1, M2, ING1, ING2, ING3"
}"""

    context_line = f"\nAdditional context from supervisor: {context}" if context else ""
    user_prompt = (
        f"Student CV(s):\n{combined_cv}"
        f"{context_line}\n\n"
        f"Generate the internship subject JSON:"
    )

    client = get_llm_client()

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=settings.GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )

            raw = response.choices[0].message.content

            # normalize unicode and clean the raw string
            import unicodedata
            clean = unicodedata.normalize('NFKC', raw.strip())

            # strip markdown code fences
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(
                    line for line in lines
                    if not line.strip().startswith("```")
                ).strip()

            # replace smart quotes and invisible characters
            clean = (
                clean
                .replace('\u201c', '"').replace('\u201d', '"')  # smart double quotes
                .replace('\u2018', "'").replace('\u2019', "'")  # smart single quotes
                .replace('\u00a0', ' ')                         # non-breaking space
                .replace('\u200b', '')                          # zero-width space
                .replace('\u200c', '').replace('\u200d', '')    # zero-width non-joiners
                .replace('\ufeff', '')                          # BOM
            )

            # extract JSON object if there is text before or after it
            import re
            json_match = re.search(r'\{.*\}', clean, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON object found in response")
            clean = json_match.group(0)
            logger.debug(f"Cleaned JSON attempt {attempt + 1}: {repr(clean[:200])}")
            
            parsed = json.loads(clean)

            required = {"titre", "description", "techno", "prerequis", "niveau"}
            missing_fields = required - set(parsed.keys())
            if missing_fields:
                raise ValueError(f"Missing fields in response: {missing_fields}")

            return {
                "titre": parsed["titre"],
                "description": parsed["description"],
                "techno": (
                    parsed["techno"]
                    if isinstance(parsed["techno"], list)
                    else [parsed["techno"]]
                ),
                "prerequis": parsed["prerequis"],
                "niveau": parsed["niveau"],
                "rawPromptUsed": user_prompt,
            }

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Generation parse error attempt {attempt + 1}: {e}")
            if attempt == 1:
                raise GenerationError(f"generation_invalid_response: {e}")
            user_prompt += (
                "\n\nIMPORTANT: Your response must be valid JSON only. "
                "No markdown, no code fences, no extra text before or after the JSON."
            )

        except APIError as e:
            logger.error(f"LLM API error: {e}")
            raise GenerationError(f"generation_failed: {e}")
