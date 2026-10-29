from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings


def _ensure_sqlite_parent(database_url: str) -> None:
    url = make_url(database_url)
    database_path = url.database
    if (
        url.get_backend_name() != "sqlite"
        or not database_path
        or database_path == ":memory:"
        or database_path.startswith("file:")
    ):
        return
    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_parent(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app import models

    models.Base.metadata.create_all(bind=engine)