from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.database import close_db, init_db
from app.routers import embed, extract, generate, health, rag, suggest
from app.security import verify_internal_secret

protected = [Depends(verify_internal_secret)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)

app.include_router(health.router)
app.include_router(extract.router, dependencies=protected)
app.include_router(embed.router, dependencies=protected)
app.include_router(suggest.router, dependencies=protected)
app.include_router(generate.router, dependencies=protected)
app.include_router(rag.router, dependencies=protected)
