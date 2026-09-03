from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import ArgumentError

from .config import settings


def _build_engine():
    url = settings.database_url
    if not url or url.startswith("@"):
        url = "sqlite:///./local.db"
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine_kwargs = {"connect_args": connect_args}
    if url.startswith("sqlite") and ":memory:" in url:
        engine_kwargs["poolclass"] = StaticPool

    try:
        return create_engine(url, **engine_kwargs)
    except (ArgumentError, ValueError) as exc:
        print(f"WARN: Invalid DATABASE_URL ({exc}), falling back to SQLite")
        fallback = create_engine(
            "sqlite:///./local.db",
            connect_args={"check_same_thread": False},
        )
        return fallback


engine = _build_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
