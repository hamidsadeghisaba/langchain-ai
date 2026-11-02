from __future__ import annotations
import logging

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

from sqlalchemy import (
    Engine,
    URL,
    and_,
    create_engine,
    event,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import IntegrityError

from service.model.task_models import (
    ClaimedTask,
    InvalidTaskTransitionError,
    Task,
    TaskNotFoundError,
    TaskStage,
    TaskStatus,
)
from service.repository.task_schema import metadata, workflow_tasks


_RESULT_COLUMNS = {
    TaskStage.ANALYZER: "analysis_result",
    TaskStage.DEVELOPER: "development_result",
    TaskStage.TESTER: "test_result",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PersistentTaskRepository:
    """Shared SQLAlchemy Core implementation for persistent task queues."""

    backend = "sqlalchemy"

    def __init__(self, engine: Engine):
        self.engine = engine
        self._initialize()

    def _initialize(self) -> None:
        metadata.create_all(self.engine)
        for index in workflow_tasks.indexes:
            index.create(self.engine, checkfirst=True)

    @staticmethod
    def _row_to_task(row: Mapping[str, Any]) -> Task:
        return Task(
            task_id=row["task_id"],
            title=row["title"],
            description=row["description"],
            stage=TaskStage(row["stage"]),
            status=TaskStatus(row["status"]),
            priority=row["priority"],
            thread_id=row["thread_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            error_message=row["error_message"],
            approved_at=row["approved_at"],
            retry_count=row["retry_count"],
            recovery_count=row["recovery_count"],
            analysis_result=row["analysis_result"],
            development_result=row["development_result"],
            test_result=row["test_result"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _get_task_from_connection(
        connection: Connection,
        task_id: str,
    ) -> Task:
        row = connection.execute(
            select(workflow_tasks).where(
                workflow_tasks.c.task_id == task_id
            )
        ).first()
        if row is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return PersistentTaskRepository._row_to_task(row._mapping)

    def create_task(
        self,
        title: str,
        description: str,
        *,
        priority: int = 0,
        submission_key: str | None = None,
    ) -> Task:
        title = title.strip()
        description = description.strip()
        if not title:
            raise ValueError("Task title cannot be empty.")
        if not description:
            raise ValueError("Task description cannot be empty.")

        task_id = uuid.uuid4().hex
        thread_id = f"task-{task_id}"
        now = _utc_now()

        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(workflow_tasks).values(
                        task_id=task_id,
                        submission_key=submission_key,
                        title=title,
                        description=description,
                        stage=TaskStage.ANALYZER.value,
                        status=TaskStatus.PENDING.value,
                        priority=int(priority),
                        thread_id=thread_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            # A concurrent submit may win the unique submission-key race
            # between the pre-check and INSERT. Return the winner's task.
            if submission_key:
                with self.engine.connect() as connection:
                    existing = connection.execute(
                        select(workflow_tasks).where(
                            workflow_tasks.c.submission_key == submission_key
                        )
                    ).first()
                if existing:
                    return self._row_to_task(existing._mapping)
            raise

        return self.get_task(task_id)

    def get_task(self, task_id: str) -> Task:
        with self.engine.connect() as connection:
            return self._get_task_from_connection(connection, task_id)

    def list_tasks(
        self,
        *,
        stage: TaskStage | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        statement = select(workflow_tasks)
        if stage is not None:
            statement = statement.where(workflow_tasks.c.stage == stage.value)
        if status is not None:
            statement = statement.where(
                workflow_tasks.c.status == status.value
            )
        statement = statement.order_by(
            workflow_tasks.c.priority.desc(),
            workflow_tasks.c.created_at.asc(),
        )

        with self.engine.connect() as connection:
            rows = connection.execute(statement).all()
        return [self._row_to_task(row._mapping) for row in rows]

    def list_pending_tasks(self, stage: TaskStage) -> list[Task]:
        return self.list_tasks(stage=stage, status=TaskStatus.PENDING)

    def claim_task(
        self,
        task_id: str,
        *,
        expected_stage: TaskStage | None = None,
        worker_id: str = "streamlit",
    ) -> ClaimedTask | None:
        """Atomically claim one queued task using a conditional update.

        The status predicate is evaluated as part of the UPDATE. SQLite
        serializes writers, while PostgreSQL locks the updated row, so exactly
        one concurrent worker can move the task from PENDING to RUNNING.
        """

        execution_token = uuid.uuid4().hex
        now = _utc_now()
        claim_conditions = [
            workflow_tasks.c.task_id == task_id,
            workflow_tasks.c.status == TaskStatus.PENDING.value,
            or_(
                workflow_tasks.c.stage != TaskStage.DEVELOPER.value,
                workflow_tasks.c.approved_at.is_not(None),
            ),
        ]
        if expected_stage is not None:
            claim_conditions.append(
                workflow_tasks.c.stage == expected_stage.value
            )

        with self.engine.begin() as connection:
            result = connection.execute(
                update(workflow_tasks)
                .where(and_(*claim_conditions))
                .values(
                    status=TaskStatus.RUNNING.value,
                    updated_at=now,
                    error_message=None,
                    execution_token=execution_token,
                    worker_id=worker_id,
                )
            )
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                return None

        return ClaimedTask(
            task=self.get_task(task_id),
            execution_token=execution_token,
        )

    def approve_task(self, task_id: str) -> Task:
        now = _utc_now()
        with self.engine.begin() as connection:
            result = connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.task_id == task_id,
                    workflow_tasks.c.stage == TaskStage.DEVELOPER.value,
                    workflow_tasks.c.status == TaskStatus.PENDING.value,
                )
                .values(
                    approved_at=now,
                    updated_at=now,
                    error_message=None,
                )
            )
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    "Only a pending Developer-stage task can be approved."
                )

        return self.get_task(task_id)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        error_message: str | None = None,
        execution_token: str | None = None,
    ) -> Task:
        now = _utc_now()
        completed_at = (
            now
            if status is TaskStatus.COMPLETED
            else workflow_tasks.c.completed_at
        )

        statement = (
            update(workflow_tasks)
            .where(workflow_tasks.c.task_id == task_id)
            .values(
                status=status.value,
                updated_at=now,
                error_message=error_message,
                execution_token=None,
                worker_id=None,
                completed_at=completed_at,
            )
        )
        if execution_token is not None:
            statement = statement.where(
                workflow_tasks.c.execution_token == execution_token
            )

        with self.engine.begin() as connection:
            result = connection.execute(statement)
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    f"Cannot update task {task_id} to {status.value}."
                )

        return self.get_task(task_id)

    def record_execution_result(
        self,
        task_id: str,
        result: str,
        *,
        execution_token: str | None = None,
    ) -> Task:
        task = self.get_task(task_id)
        column = _RESULT_COLUMNS[task.stage]
        statement = (
            update(workflow_tasks)
            .where(
                workflow_tasks.c.task_id == task_id,
                workflow_tasks.c.status == TaskStatus.RUNNING.value,
            )
            .values(
                **{
                    column: result,
                    "updated_at": _utc_now(),
                }
            )
        )
        if execution_token is not None:
            statement = statement.where(
                workflow_tasks.c.execution_token == execution_token
            )

        with self.engine.begin() as connection:
            updated = connection.execute(statement)
            if updated.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    f"Cannot record execution result for task {task_id}."
                )

        return self.get_task(task_id)

    def move_to_next_stage(
        self,
        task_id: str,
        result: str,
        *,
        execution_token: str,
    ) -> Task:
        """Persist a successful stage result and advance in one transaction."""

        with self.engine.connect() as connection:
            row = connection.execute(
                select(workflow_tasks).where(
                    workflow_tasks.c.task_id == task_id
                )
            ).first()
            if row is None:
                raise TaskNotFoundError(f"Task not found: {task_id}")

        task = self._row_to_task(row._mapping)
        if task.status is not TaskStatus.RUNNING:
            raise InvalidTaskTransitionError(
                "A stage result can only be recorded for a RUNNING task."
            )
        if row.execution_token != execution_token:
            raise InvalidTaskTransitionError(
                "The task execution token is no longer current."
            )

        now = _utc_now()
        result_column = _RESULT_COLUMNS[task.stage]
        values: dict[str, Any] = {
            result_column: result,
            "updated_at": now,
            "error_message": None,
            "execution_token": None,
            "worker_id": None,
        }
        if task.stage is TaskStage.ANALYZER:
            values.update(
                stage=TaskStage.DEVELOPER.value,
                status=TaskStatus.PENDING.value,
                approved_at=None,
            )
        elif task.stage is TaskStage.DEVELOPER:
            values.update(
                stage=TaskStage.TESTER.value,
                status=TaskStatus.PENDING.value,
            )
        else:
            values.update(
                status=TaskStatus.COMPLETED.value,
                completed_at=now,
            )

        with self.engine.begin() as connection:
            updated = connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.task_id == task_id,
                    workflow_tasks.c.stage == task.stage.value,
                    workflow_tasks.c.status == TaskStatus.RUNNING.value,
                    workflow_tasks.c.execution_token == execution_token,
                )
                .values(**values)
            )
            if updated.rowcount != 1:
                raise InvalidTaskTransitionError(
                    f"Task {task_id} could not be advanced."
                )

        return self.get_task(task_id)

    def record_error(
        self,
        task_id: str,
        error_message: str,
        *,
        execution_token: str,
    ) -> Task:
        """Fail the current stage without advancing it."""

        task = self.get_task(task_id)
        with self.engine.begin() as connection:
            result = connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.task_id == task_id,
                    workflow_tasks.c.status == TaskStatus.RUNNING.value,
                    workflow_tasks.c.stage == task.stage.value,
                    workflow_tasks.c.execution_token == execution_token,
                )
                .values(
                    status=TaskStatus.FAILED.value,
                    updated_at=_utc_now(),
                    error_message=error_message,
                    execution_token=None,
                    worker_id=None,
                )
            )
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    f"Could not record the failure for task {task_id}."
                )

        return self.get_task(task_id)

    def fail_awaiting_review(
        self,
        task_id: str,
        error_message: str,
    ) -> Task:
        """Fail a rejected analysis and return it to the Analyzer queue on retry."""

        with self.engine.begin() as connection:
            result = connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.task_id == task_id,
                    workflow_tasks.c.stage == TaskStage.DEVELOPER.value,
                    workflow_tasks.c.status == TaskStatus.PENDING.value,
                    workflow_tasks.c.approved_at.is_(None),
                )
                .values(
                    stage=TaskStage.ANALYZER.value,
                    status=TaskStatus.FAILED.value,
                    updated_at=_utc_now(),
                    error_message=error_message,
                    approved_at=None,
                    execution_token=None,
                    worker_id=None,
                )
            )
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    "Only an unapproved Developer-stage task can be rejected."
                )

        return self.get_task(task_id)

    def retry_task(self, task_id: str) -> Task:
        """Requeue a failed task in place, without inserting a duplicate row."""

        task = self.get_task(task_id)
        if task.status is not TaskStatus.FAILED:
            raise InvalidTaskTransitionError(
                "Only a FAILED task can be retried."
            )

        target_stage = task.stage
        approved_at = task.approved_at
        if task.stage is TaskStage.DEVELOPER and task.approved_at is None:
            target_stage = TaskStage.ANALYZER

        with self.engine.begin() as connection:
            result = connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.task_id == task_id,
                    workflow_tasks.c.status == TaskStatus.FAILED.value,
                )
                .values(
                    stage=target_stage.value,
                    status=TaskStatus.PENDING.value,
                    updated_at=_utc_now(),
                    error_message=None,
                    approved_at=approved_at,
                    retry_count=workflow_tasks.c.retry_count + 1,
                    execution_token=None,
                    worker_id=None,
                )
            )
            if result.rowcount != 1:
                self._get_task_from_connection(connection, task_id)
                raise InvalidTaskTransitionError(
                    f"Could not retry task {task_id}."
                )

        return self.get_task(task_id)

    def recover_interrupted_tasks(self) -> list[Task]:
        """Requeue RUNNING tasks after an application interruption."""

        message = (
            "Recovered after the application stopped while this stage was RUNNING."
        )
        with self.engine.connect() as connection:
            task_ids = list(
                connection.scalars(
                    select(workflow_tasks.c.task_id)
                    .where(
                        workflow_tasks.c.status == TaskStatus.RUNNING.value
                    )
                    .order_by(
                        workflow_tasks.c.priority.desc(),
                        workflow_tasks.c.created_at.asc(),
                    )
                )
            )
        if not task_ids:
            return []

        with self.engine.begin() as connection:
            connection.execute(
                update(workflow_tasks)
                .where(
                    workflow_tasks.c.status == TaskStatus.RUNNING.value
                )
                .values(
                    status=TaskStatus.PENDING.value,
                    updated_at=_utc_now(),
                    error_message=message,
                    recovery_count=workflow_tasks.c.recovery_count + 1,
                    execution_token=None,
                    worker_id=None,
                )
            )
        return [self.get_task(task_id) for task_id in task_ids]

    def close(self) -> None:
        self.engine.dispose()


class SQLiteTaskRepository(PersistentTaskRepository):
    """SQLite configuration with compatibility and wait pragmas."""

    backend = "sqlite"

    def __init__(
        self,
        db_path: str | Path,
        *,
        database_url: str | URL | None = None,
    ):
        if database_url is not None:
            url = make_url(str(database_url))
            if url.get_backend_name() != "sqlite":
                raise ValueError(
                    "SQLiteTaskRepository requires a SQLite database URL."
                )
            if not url.database:
                raise ValueError(
                    "The SQLite database URL must include a file path."
                )
            self.db_path = Path(url.database).resolve()
        else:
            self.db_path = Path(db_path).resolve()
            url = URL.create(
                "sqlite+pysqlite",
                database=str(self.db_path),
            )

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url,
            connect_args={
                "timeout": 5.0,
                "check_same_thread": False,
            },
            pool_pre_ping=True,
        )

        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA busy_timeout = 5000")
            finally:
                cursor.close()

        super().__init__(engine)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA journal_mode = WAL")


class PostgreSQLTaskRepository(PersistentTaskRepository):
    """PostgreSQL configuration using a pooled psycopg connection."""

    backend = "postgres"

    def __init__(
        self,
        database_url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
    ):
        url = make_url(database_url)
        if url.get_backend_name() in {"postgres", "postgresql"}:
            url = url.set(drivername="postgresql+psycopg")
        if url.get_backend_name() != "postgresql":
            raise ValueError(
                "PostgreSQLTaskRepository requires a PostgreSQL database URL."
            )

        self.database_url = url.render_as_string(hide_password=False)
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
        super().__init__(engine)

# Preserve the previous SQLite constructor/import while directing new code to
# PersistentTaskRepository and the backend-specific classes.
PersistantTaskRepository = SQLiteTaskRepository


def create_task_repository(
    *,
    backend: str | None = None,
    sqlite_db_path: str | Path,
    database_url: str | None = None,
) -> PersistentTaskRepository:
    """Build a repository from ``TASK_REPOSITORY_BACKEND`` configuration."""

    backend_name = (
        backend or os.environ.get("TASK_REPOSITORY_BACKEND", "sqlite")
    ).strip().lower()

    logging.info(os.getenv("TASK_REPOSITORY_BACKEND"))
    logging.info(backend_name)

    if backend_name == "sqlite":
        if database_url:
            url = make_url(database_url)
            if url.get_backend_name() != "sqlite":
                raise ValueError(
                    "TASK_DATABASE_URL must be a SQLite URL when "
                    "TASK_REPOSITORY_BACKEND=sqlite."
                )
        return SQLiteTaskRepository(
            sqlite_db_path,
            database_url=database_url,
        )

    if backend_name == "postgres":
        if not database_url:
            raise RuntimeError(
                "TASK_DATABASE_URL is required when "
                "TASK_REPOSITORY_BACKEND=postgres."
            )
        pool_size = int(os.environ.get("TASK_DB_POOL_SIZE", "5"))
        max_overflow = int(os.environ.get("TASK_DB_MAX_OVERFLOW", "10"))
        return PostgreSQLTaskRepository(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )

    raise ValueError(
        "TASK_REPOSITORY_BACKEND must be either 'sqlite' or 'postgres'."
    )


@contextmanager
def task_repository(
    *,
    backend: str | None = None,
    sqlite_db_path: str | Path,
    database_url: str | None = None,
) -> Iterator[PersistentTaskRepository]:
    """Context manager for scripts that own a short-lived repository."""

    repository = create_task_repository(
        backend=backend,
        sqlite_db_path=sqlite_db_path,
        database_url=database_url,
    )
    try:
        yield repository
    finally:
        repository.close()
