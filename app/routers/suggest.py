from fastapi import APIRouter, Depends, HTTPException
from app.security import verify_internal_secret
from app.services.matcher import get_suggestions, NoEmbeddingError

router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.get("/suggest/{user_id}")
async def suggest(user_id: str):
    try:
        suggestions = await get_suggestions(user_id)
        return {"suggestions": suggestions}
    except NoEmbeddingError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_embedding",
                "detail": "Student CV has not been processed yet",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "suggestion_failed", "detail": str(e)},
        )
