"""SQLAlchemy engine/session setup. SQLite by default; any SQLAlchemy URL works."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def configure(url: str) -> Engine:
    """(Re)create the engine. Called at startup and by tests with an isolated DB."""
    global _engine, _SessionLocal
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        path = url.replace("sqlite:///", "", 1)
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(url, connect_args=connect_args, future=True)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _fk_on(dbapi_conn, _):  # enforce foreign keys / cascades in SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def init_db() -> None:
    from backend.app import models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=get_engine())


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Database not configured")
    return _engine


def session_factory() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Database not configured")
    return _SessionLocal()


def get_db() -> Iterator[Session]:
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
