from fastapi import APIRouter, Depends, HTTPException
from app.security import verify_internal_secret
from app.services.rag_service import ingest_document, answer_question
from app.models.requests import RagIngestRequest, RagQueryRequest
from app.models.responses import RagIngestResponse, RagQueryResponse

router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.post("/rag/documents", response_model=RagIngestResponse)
async def ingest(body: RagIngestRequest):
    try:
        chunks_stored = await ingest_document(
            file_path=body.filePath,
            document_name=body.documentName,
            document_type=body.documentType,
        )
        return RagIngestResponse(success=True, chunksIndexed=chunks_stored)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "file_not_found", "detail": f"No file at {body.filePath}"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={"error": "extraction_failed", "detail": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "ingest_failed", "detail": str(e)},
        )


@router.post("/rag/query", response_model=RagQueryResponse)
async def query(body: RagQueryRequest):
    try:
        result = await answer_question(
            question=body.question,
            user_id=body.userId,
        )
        return RagQueryResponse(**result)
    except RuntimeError as e:
        raise HTTPException(
            status_code=502,
            detail={"error": "generation_failed", "detail": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "rag_failed", "detail": str(e)},
        )
