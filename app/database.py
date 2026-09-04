from sqlalchemy import create_engine, text
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


def _table_columns(conn, table: str) -> set[str]:
    """Return the set of column names for a table, dialect-agnostic."""
    if conn.dialect.name == "sqlite":
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {row[1] for row in rows}
    rows = conn.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t"
        ),
        {"t": table},
    ).fetchall()
    return {row[0] for row in rows}


def ensure_schema(bind=None):
    """Idempotent additive migrations for the tickets table.

    create_all() only creates missing tables, not missing columns on existing
    tables. This adds any new additive columns that may be absent (e.g. after a
    rolling deploy) without destroying existing data. It is dialect-aware:
    SQLite has no ``ADD COLUMN IF NOT EXISTS`` (that is a Postgres extension),
    so column presence is checked first via introspection instead.
    """
    eng = bind or engine
    # name -> SQL column definition
    additive_columns = {
        "ai_provider": "VARCHAR NOT NULL DEFAULT 'unknown'",
    }

    with eng.begin() as conn:
        existing = _table_columns(conn, "tickets")
        for name, definition in additive_columns.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {name} {definition}"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
