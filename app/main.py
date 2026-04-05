from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import SessionLocal
from app.routers import artists, charts, collaborators, releases, songs

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

app.include_router(artists.router)
app.include_router(collaborators.router)
app.include_router(releases.router)
app.include_router(songs.router)
app.include_router(charts.router)


@app.get("/health", tags=["health"])
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
