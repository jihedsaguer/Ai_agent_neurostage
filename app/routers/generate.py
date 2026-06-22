from fastapi import APIRouter, Depends, HTTPException
from app.security import verify_internal_secret
from app.services.generator import (
    generate_subject_draft,
    StudentNotFoundError,
    GenerationError,
)
from app.models.requests import GenerateSubjectRequest

router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.post("/generate/subject-from-cv")
async def generate_subject(body: GenerateSubjectRequest):
    try:
        result = await generate_subject_draft(
            student_ids=body.studentIds,
            encadreur_id=body.encadreurId,
            context=body.context,
        )
        return result
    except StudentNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"error": "student_not_found", "detail": str(e)},
        )
    except GenerationError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "generation_failed", "detail": str(e)},
        )
