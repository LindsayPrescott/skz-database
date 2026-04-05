from fastapi import APIRouter

from app.routers import artists, charts, collaborators, releases, songs

router = APIRouter(prefix="/v1")
router.include_router(artists.router)
router.include_router(charts.router)
router.include_router(collaborators.router)
router.include_router(releases.router)
router.include_router(songs.router)
