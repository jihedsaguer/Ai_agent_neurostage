import hmac

from fastapi import Header, HTTPException

from app.config import settings


async def verify_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> None:
    if not x_internal_secret or not hmac.compare_digest(
        x_internal_secret, settings.INTERNAL_SECRET
    ):
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
