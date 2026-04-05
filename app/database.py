from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings

# Use LOCAL_DATABASE_URL when running scripts directly on the host machine
# (scrapers, one-off commands). Falls back to DATABASE_URL inside Docker.
_url = settings.local_database_url or settings.database_url
engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency. Yields a database session and guarantees
    it closes after the request finishes, even if an exception occurs.
    """
    db: Session = SessionLocal()
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()
