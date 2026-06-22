from fastapi import APIRouter, Depends, HTTPException
from app.security import verify_internal_secret
from app.services.extractor import extract_text
from app.models.requests import ExtractRequest
from app.models.responses import ExtractResponse

router = APIRouter(
    prefix='',
    dependencies=[Depends(verify_internal_secret)],
)


@router.post('/extract', response_model=ExtractResponse)
async def extract(body: ExtractRequest):
    try:
        result = extract_text(body.filePath, body.fileType)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={'error': 'file_not_found', 'detail': f'No file at {body.filePath}'},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={'error': 'extraction_failed', 'detail': str(e)},
        )

    return ExtractResponse(
        extractedText=result['text'],
        wordCount=result['word_count'],
        language=result['language'],
    )