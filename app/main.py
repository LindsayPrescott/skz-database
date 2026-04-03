from fastapi import FastAPI

from app.routers import artists, releases, songs, tracks

app = FastAPI(
    title="SKZ Database API",
    description="Stray Kids discography — albums, songs, credits, chart data.",
    version="0.1.0",
)

app.include_router(artists.router)
app.include_router(releases.router)
app.include_router(songs.router)
app.include_router(tracks.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
