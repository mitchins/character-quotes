"""Database setup; SQLite is deliberately the initial deployment target."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def database_url(value: str | None = None) -> str:
    configured = value or os.getenv("CHARACTER_QUOTES_DATABASE")
    if not configured:
        return "sqlite:///character_quotes.sqlite3"
    return (
        configured
        if "://" in configured
        else f"sqlite:///{Path(configured).expanduser()}"
    )


def make_engine(url: str | None = None) -> Engine:
    resolved_url = database_url(url)
    options: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if resolved_url == "sqlite://":
        options["poolclass"] = StaticPool
    engine = create_engine(resolved_url, **options)
    if engine.url.drivername == "sqlite":

        @event.listens_for(engine, "connect")
        def configure_sqlite(dbapi_connection: object, _: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def initialize(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def begin_daily_assignment(session: Session) -> None:
    """Serialize SQLite selection before reading its rolling window."""
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
