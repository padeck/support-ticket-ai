import sqlite3

from sqlalchemy import create_engine, text

from app.database import _table_columns, ensure_schema


def _build_stale_db(path: str):
    """Create a tickets table WITHOUT the ai_provider column (as an older app version)."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE tickets (
            id INTEGER PRIMARY KEY,
            ticket_id VARCHAR NOT NULL,
            request_text TEXT NOT NULL,
            category VARCHAR NOT NULL,
            priority VARCHAR NOT NULL,
            assigned_team VARCHAR NOT NULL,
            summary TEXT NOT NULL,
            status VARCHAR NOT NULL DEFAULT 'open',
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )
    conn.execute(
        "INSERT INTO tickets (ticket_id, request_text, category, priority, assigned_team, summary, status) "
        "VALUES (?,?,?,?,?,?,?)",
        ("T-OLD1", "Mein Konto ist gesperrt", "account_access", "high", "identity-operations", "Alt", "open"),
    )
    conn.commit()
    conn.close()


def test_ensure_schema_adds_missing_column_to_sqlite(tmp_path):
    db_path = str(tmp_path / "stale.db")
    _build_stale_db(db_path)

    engine = create_engine(f"sqlite:///{db_path}")

    with engine.begin() as conn:
        assert "ai_provider" not in _table_columns(conn, "tickets")

    ensure_schema(engine)

    with engine.begin() as conn:
        cols = _table_columns(conn, "tickets")
        assert "ai_provider" in cols
        row = conn.execute(text("SELECT ai_provider FROM tickets WHERE ticket_id = 'T-OLD1'")).fetchone()
        assert row[0] == "unknown"


def test_ensure_schema_is_idempotent(tmp_path):
    db_path = str(tmp_path / "stale.db")
    _build_stale_db(db_path)
    engine = create_engine(f"sqlite:///{db_path}")
    ensure_schema(engine)
    ensure_schema(engine)  # second run must not raise
