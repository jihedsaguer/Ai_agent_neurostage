import logging
import time
from fastapi import APIRouter, Depends, HTTPException
from app.security import verify_internal_secret
from app.database import get_pool
from app.services.embedder import embed_and_store_student, embed_and_store_subject
from app.models.requests import EmbedStudentRequest, EmbedSubjectRequest, EmbedSubjectsBulkRequest
from app.models.responses import EmbedResponse, BulkEmbedResponse

router = APIRouter(dependencies=[Depends(verify_internal_secret)])
logger = logging.getLogger(__name__)


@router.post("/embed/student", response_model=EmbedResponse)
async def embed_student(body: EmbedStudentRequest):
    try:
        pool = get_pool()
        await embed_and_store_student(
            pool,
            body.userId,
            body.extractedText,
            body.skills,
            body.university,
            body.specialization,
            body.level,
        )
        return EmbedResponse(success=True)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail={"error": "embedding_failed", "detail": str(e)})


@router.post("/embed/subject", response_model=EmbedResponse)
async def embed_subject(body: EmbedSubjectRequest):
    try:
        pool = get_pool()
        await embed_and_store_subject(
            pool,
            body.subjectId,
            body.titre,
            body.description,
            body.techno,
            body.prerequis,
            body.niveau,
        )
        return EmbedResponse(success=True)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail={"error": "embedding_failed", "detail": str(e)})


@router.post("/embed/subjects/bulk", response_model=BulkEmbedResponse)
async def embed_subjects_bulk(body: EmbedSubjectsBulkRequest):
    pool = get_pool()
    start = time.time()
    indexed = 0
    failed = 0

    for subject in body.subjects:
        try:
            await embed_and_store_subject(
                pool,
                subject.subjectId,
                subject.titre,
                subject.description,
                subject.techno,
                subject.prerequis,
                subject.niveau,
            )
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to embed subject {subject.subjectId}: {e}")
            failed += 1

    duration = round(time.time() - start, 2)
    return BulkEmbedResponse(indexed=indexed, failed=failed, duration=duration)