from __future__ import annotations

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Any, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from psycopg import Connection
from psycopg.rows import dict_row
from sqlalchemy.engine import make_url

import config


class CheckpointStore(Protocol):
    """Application-owned LangGraph checkpointer and its database connection."""

    connection: Any
    checkpointer: BaseCheckpointSaver

    @property
    def saver(self) -> BaseCheckpointSaver: ...

    def close(self) -> None: ...

    def __enter__(self) -> CheckpointStore: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class _ManagedCheckpointStore:
    """Shared connection lifecycle for concrete checkpoint stores."""

    connection: Any
    checkpointer: BaseCheckpointSaver
    _closed = False

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.connection.close()

    @property
    def saver(self) -> BaseCheckpointSaver:
        """Preserve the previous store attribute used by existing callers."""

        return self.checkpointer

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class SQLiteCheckpointStore(_ManagedCheckpointStore):
    """Own a long-lived SQLite connection used by LangGraph."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            check_same_thread=False,
        )
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            checkpointer = SqliteSaver(connection)
            checkpointer.setup()
        except Exception:
            connection.close()
            raise

        self.connection = connection
        self.checkpointer = checkpointer


class PostgresCheckpointStore(_ManagedCheckpointStore):
    """Own a long-lived psycopg connection used by LangGraph."""

    def __init__(self, database_url: str):
        url = make_url(database_url)
        if url.get_backend_name() not in {"postgres", "postgresql"}:
            raise ValueError(
                "PostgresCheckpointStore requires a PostgreSQL database URL."
            )

        # psycopg accepts libpq URLs, not SQLAlchemy's driver-qualified form.
        connection_url = url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        connection = Connection.connect(
            connection_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        try:
            checkpointer = PostgresSaver(connection)
            checkpointer.setup()
        except Exception:
            connection.close()
            raise

        self.connection = connection
        self.checkpointer = checkpointer


def create_checkpoint_store(
    *,
    backend: str | None = None,
    sqlite_path: str | Path | None = None,
    postgres_url: str | None = None,
) -> CheckpointStore:
    """Build a checkpointer from ``CHECKPOINT_BACKEND`` configuration."""

    backend_name = (
        config.CHECKPOINT_BACKEND if backend is None else backend
    ).strip().lower()

    if backend_name == "sqlite":
        selected_path = (
            config.CHECKPOINT_SQLITE_PATH
            if sqlite_path is None
            else sqlite_path
        )
        return SQLiteCheckpointStore(selected_path)

    if backend_name == "postgres":
        selected_url = (
            config.CHECKPOINT_POSTGRES_URL
            if postgres_url is None
            else postgres_url
        )
        if not selected_url:
            raise RuntimeError(
                "CHECKPOINT_POSTGRES_URL is required when "
                "CHECKPOINT_BACKEND=postgres."
            )
        return PostgresCheckpointStore(selected_url)

    raise ValueError(
        "CHECKPOINT_BACKEND must be either 'sqlite' or 'postgres'."
    )
