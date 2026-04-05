from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# Use LOCAL_DATABASE_URL when running scripts directly on the host machine
# (scrapers, one-off commands). Falls back to DATABASE_URL inside Docker.
_url = settings.local_database_url or settings.database_url
_async_url = _url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Sync engine — used by scrapers and one-off scripts only
engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async engine — used by the FastAPI application
async_engine = create_async_engine(_async_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_db():
    """
    FastAPI dependency. Yields an async database session and guarantees
    it closes after the request finishes, even if an exception occurs.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except:
            await db.rollback()
            raise


def get_db():
    """
    Sync FastAPI dependency. Retained during async migration — removed in Step 6.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()
