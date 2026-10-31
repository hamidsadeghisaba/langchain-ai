from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional


class TaskStage(str, Enum):
    ANALYZER = "ANALYZER"
    DEVELOPER = "DEVELOPER"
    TESTER = "TESTER"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskQueueError(Exception):
    """Base exception for task queue operations."""


class TaskNotFoundError(TaskQueueError):
    pass


class InvalidTaskTransitionError(TaskQueueError):
    pass


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    description: str
    stage: TaskStage
    status: TaskStatus
    priority: int
    thread_id: str
    created_at: str
    updated_at: str
    error_message: Optional[str]
    approved_at: Optional[str]
    retry_count: int
    recovery_count: int
    analysis_result: str
    development_result: str
    test_result: str
    completed_at: Optional[str]

    @property
    def awaiting_approval(self) -> bool:
        return (
            self.stage is TaskStage.DEVELOPER
            and self.status is TaskStatus.PENDING
            and self.approved_at is None
        )


@dataclass(frozen=True)
class ClaimedTask:
    task: Task
    execution_token: str


_RESULT_COLUMNS = {
    TaskStage.ANALYZER: "analysis_result",
    TaskStage.DEVELOPER: "development_result",
    TaskStage.TESTER: "test_result",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SQLiteTaskRepository:
    """Durable, SQLite-backed stage queues with atomic task claims."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_tasks (
                    task_id TEXT PRIMARY KEY,
                    submission_key TEXT UNIQUE,
                    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
                    description TEXT NOT NULL CHECK (length(trim(description)) > 0),
                    stage TEXT NOT NULL CHECK (
                        stage IN ('ANALYZER', 'DEVELOPER', 'TESTER')
                    ),
                    status TEXT NOT NULL CHECK (
                        status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')
                    ),
                    priority INTEGER NOT NULL DEFAULT 0,
                    thread_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_message TEXT,
                    approved_at TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    recovery_count INTEGER NOT NULL DEFAULT 0,
                    analysis_result TEXT NOT NULL DEFAULT '',
                    development_result TEXT NOT NULL DEFAULT '',
                    test_result TEXT NOT NULL DEFAULT '',
                    completed_at TEXT,
                    execution_token TEXT,
                    worker_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_workflow_tasks_queue
                ON workflow_tasks (
                    stage,
                    status,
                    priority DESC,
                    created_at ASC
                );

                CREATE INDEX IF NOT EXISTS idx_workflow_tasks_thread
                ON workflow_tasks (thread_id);
                """
            )

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
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
            with self._connection() as connection:
                if submission_key:
                    existing = connection.execute(
                        """
                        SELECT *
                        FROM workflow_tasks
                        WHERE submission_key = ?
                        """,
                        (submission_key,),
                    ).fetchone()
                    if existing:
                        return self._row_to_task(existing)

                connection.execute(
                    """
                    INSERT INTO workflow_tasks (
                        task_id,
                        submission_key,
                        title,
                        description,
                        stage,
                        status,
                        priority,
                        thread_id,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        submission_key,
                        title,
                        description,
                        TaskStage.ANALYZER.value,
                        TaskStatus.PENDING.value,
                        int(priority),
                        thread_id,
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError:
            # A concurrent submit may win the unique submission-key race
            # between the pre-check and INSERT. Return the winner's task.
            if submission_key:
                with self._connection() as connection:
                    existing = connection.execute(
                        """
                        SELECT *
                        FROM workflow_tasks
                        WHERE submission_key = ?
                        """,
                        (submission_key,),
                    ).fetchone()
                if existing:
                    return self._row_to_task(existing)
            raise

        return self.get_task(task_id)

    def get_task(self, task_id: str) -> Task:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

        if row is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return self._row_to_task(row)

    def list_tasks(
        self,
        *,
        stage: TaskStage | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        clauses: list[str] = []
        parameters: list[str] = []

        if stage is not None:
            clauses.append("stage = ?")
            parameters.append(stage.value)
        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM workflow_tasks
                {where}
                ORDER BY priority DESC, created_at ASC
                """,
                parameters,
            ).fetchall()

        return [self._row_to_task(row) for row in rows]

    def list_pending_tasks(self, stage: TaskStage) -> list[Task]:
        return self.list_tasks(stage=stage, status=TaskStatus.PENDING)

    def claim_task(
        self,
        task_id: str,
        *,
        expected_stage: TaskStage | None = None,
        worker_id: str = "streamlit",
    ) -> ClaimedTask | None:
        """Atomically claim one queued task.

        Developer tasks can only be claimed after human approval. A second
        worker receives ``None`` because the first claim moves the row to
        RUNNING under the same SQLite write transaction.
        """

        connection = self._connect()
        execution_token = uuid.uuid4().hex
        now = _utc_now()

        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM workflow_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            if row is None:
                connection.rollback()
                raise TaskNotFoundError(f"Task not found: {task_id}")

            task = self._row_to_task(row)
            if task.status is not TaskStatus.PENDING:
                connection.rollback()
                return None
            if expected_stage is not None and task.stage is not expected_stage:
                connection.rollback()
                return None
            if task.stage is TaskStage.DEVELOPER and task.approved_at is None:
                connection.rollback()
                return None

            connection.execute(
                """
                UPDATE workflow_tasks
                SET status = ?,
                    updated_at = ?,
                    error_message = NULL,
                    execution_token = ?,
                    worker_id = ?
                WHERE task_id = ?
                  AND status = ?
                """,
                (
                    TaskStatus.RUNNING.value,
                    now,
                    execution_token,
                    worker_id,
                    task_id,
                    TaskStatus.PENDING.value,
                ),
            )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

        return ClaimedTask(
            task=self.get_task(task_id),
            execution_token=execution_token,
        )

    def approve_task(self, task_id: str) -> Task:
        now = _utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_tasks
                SET approved_at = ?,
                    updated_at = ?,
                    error_message = NULL
                WHERE task_id = ?
                  AND stage = ?
                  AND status = ?
                """,
                (
                    now,
                    now,
                    task_id,
                    TaskStage.DEVELOPER.value,
                    TaskStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
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
        sql = """
            UPDATE workflow_tasks
            SET status = ?,
                updated_at = ?,
                error_message = ?,
                execution_token = NULL,
                worker_id = NULL,
                completed_at = CASE
                    WHEN ? = 'COMPLETED' THEN ?
                    ELSE completed_at
                END
            WHERE task_id = ?
        """
        parameters: list[object] = [
            status.value,
            now,
            error_message,
            status.value,
            now,
            task_id,
        ]

        if execution_token is not None:
            sql += " AND execution_token = ?"
            parameters.append(execution_token)

        with self._connection() as connection:
            cursor = connection.execute(sql, parameters)
            if cursor.rowcount != 1:
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
        sql = f"""
            UPDATE workflow_tasks
            SET {column} = ?,
                updated_at = ?
            WHERE task_id = ?
              AND status = ?
        """
        parameters: list[object] = [
            result,
            _utc_now(),
            task_id,
            TaskStatus.RUNNING.value,
        ]

        if execution_token is not None:
            sql += " AND execution_token = ?"
            parameters.append(execution_token)

        with self._connection() as connection:
            cursor = connection.execute(sql, parameters)
            if cursor.rowcount != 1:
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

        connection = self._connect()
        now = _utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT *
                FROM workflow_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise TaskNotFoundError(f"Task not found: {task_id}")

            task = self._row_to_task(row)
            if task.status is not TaskStatus.RUNNING:
                raise InvalidTaskTransitionError(
                    "A stage result can only be recorded for a RUNNING task."
                )

            current_token = connection.execute(
                """
                SELECT execution_token
                FROM workflow_tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()["execution_token"]
            if current_token != execution_token:
                raise InvalidTaskTransitionError(
                    "The task execution token is no longer current."
                )

            result_column = _RESULT_COLUMNS[task.stage]
            if task.stage is TaskStage.ANALYZER:
                updated = connection.execute(
                    f"""
                    UPDATE workflow_tasks
                    SET {result_column} = ?,
                        stage = ?,
                        status = ?,
                        updated_at = ?,
                        error_message = NULL,
                        execution_token = NULL,
                        worker_id = NULL,
                        approved_at = NULL
                    WHERE task_id = ?
                    """,
                    (
                        result,
                        TaskStage.DEVELOPER.value,
                        TaskStatus.PENDING.value,
                        now,
                        task_id,
                    ),
                )
            elif task.stage is TaskStage.DEVELOPER:
                updated = connection.execute(
                    f"""
                    UPDATE workflow_tasks
                    SET {result_column} = ?,
                        stage = ?,
                        status = ?,
                        updated_at = ?,
                        error_message = NULL,
                        execution_token = NULL,
                        worker_id = NULL
                    WHERE task_id = ?
                    """,
                    (
                        result,
                        TaskStage.TESTER.value,
                        TaskStatus.PENDING.value,
                        now,
                        task_id,
                    ),
                )
            else:
                updated = connection.execute(
                    f"""
                    UPDATE workflow_tasks
                    SET {result_column} = ?,
                        status = ?,
                        updated_at = ?,
                        completed_at = ?,
                        error_message = NULL,
                        execution_token = NULL,
                        worker_id = NULL
                    WHERE task_id = ?
                    """,
                    (
                        result,
                        TaskStatus.COMPLETED.value,
                        now,
                        now,
                        task_id,
                    ),
                )

            if updated.rowcount != 1:
                raise InvalidTaskTransitionError(
                    f"Task {task_id} could not be advanced."
                )
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

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
        now = _utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_tasks
                SET status = ?,
                    updated_at = ?,
                    error_message = ?,
                    execution_token = NULL,
                    worker_id = NULL
                WHERE task_id = ?
                  AND status = ?
                  AND stage = ?
                  AND execution_token = ?
                """,
                (
                    TaskStatus.FAILED.value,
                    now,
                    error_message,
                    task_id,
                    TaskStatus.RUNNING.value,
                    task.stage.value,
                    execution_token,
                ),
            )
            if cursor.rowcount != 1:
                raise InvalidTaskTransitionError(
                    f"Could not record the failure for task {task_id}."
                )

        return self.get_task(task_id)

    def fail_awaiting_review(self, task_id: str, error_message: str) -> Task:
        """Fail a rejected analysis and return it to the Analyzer queue on retry."""

        now = _utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_tasks
                SET stage = ?,
                    status = ?,
                    updated_at = ?,
                    error_message = ?,
                    approved_at = NULL,
                    execution_token = NULL,
                    worker_id = NULL
                WHERE task_id = ?
                  AND stage = ?
                  AND status = ?
                  AND approved_at IS NULL
                """,
                (
                    TaskStage.ANALYZER.value,
                    TaskStatus.FAILED.value,
                    now,
                    error_message,
                    task_id,
                    TaskStage.DEVELOPER.value,
                    TaskStatus.PENDING.value,
                ),
            )
            if cursor.rowcount != 1:
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

        now = _utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """
                UPDATE workflow_tasks
                SET stage = ?,
                    status = ?,
                    updated_at = ?,
                    error_message = NULL,
                    approved_at = ?,
                    retry_count = retry_count + 1,
                    execution_token = NULL,
                    worker_id = NULL
                WHERE task_id = ?
                  AND status = ?
                """,
                (
                    target_stage.value,
                    TaskStatus.PENDING.value,
                    now,
                    approved_at,
                    task_id,
                    TaskStatus.FAILED.value,
                ),
            )
            if cursor.rowcount != 1:
                raise InvalidTaskTransitionError(
                    f"Could not retry task {task_id}."
                )

        return self.get_task(task_id)

    def recover_interrupted_tasks(self) -> list[Task]:
        """Requeue RUNNING tasks after a process interruption.

        Call this once when the application-owned runtime starts. The task keeps
        its stage, agent results, approval, and checkpoint thread, so it can
        resume without silently disappearing or being duplicated.
        """

        now = _utc_now()
        message = (
            "Recovered after the application stopped while this stage was RUNNING."
        )
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT task_id
                FROM workflow_tasks
                WHERE status = ?
                ORDER BY priority DESC, created_at ASC
                """,
                (TaskStatus.RUNNING.value,),
            ).fetchall()
            task_ids = [row["task_id"] for row in rows]

            if task_ids:
                connection.execute(
                    """
                    UPDATE workflow_tasks
                    SET status = ?,
                        updated_at = ?,
                        error_message = ?,
                        recovery_count = recovery_count + 1,
                        execution_token = NULL,
                        worker_id = NULL
                    WHERE status = ?
                    """,
                    (
                        TaskStatus.PENDING.value,
                        now,
                        message,
                        TaskStatus.RUNNING.value,
                    ),
                )

        return [self.get_task(task_id) for task_id in task_ids]
