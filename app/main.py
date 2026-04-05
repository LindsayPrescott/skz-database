from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.routers import router as v1_router

app = FastAPI(
    title="SKZ Database API",
    description="Stray Kids discography — albums, songs, credits, chart data.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(v1_router)


@app.get("/health", tags=["health"])
async def health_check():
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
