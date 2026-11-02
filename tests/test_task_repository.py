from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from service.model.task_queue import (
    InvalidTaskTransitionError,
    PostgreSQLTaskRepository,
    SQLiteTaskRepository,
    TaskStage,
    TaskStatus,
    create_task_repository,
)
from task_schema import workflow_tasks
from service.task_service import TaskWorkflowRuntime


def _postgres_test_url(raw_url: str):
    url = make_url(raw_url)
    if url.get_backend_name() in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return url


@pytest.fixture(params=["sqlite", "postgres"])
def repository(request, tmp_path):
    if request.param == "sqlite":
        repo = SQLiteTaskRepository(tmp_path / "workflow.sqlite3")
        try:
            yield repo
        finally:
            repo.close()
        return

    raw_url = os.environ.get("TASK_TEST_POSTGRES_URL")
    if not raw_url:
        pytest.skip(
            "Set TASK_TEST_POSTGRES_URL to run PostgreSQL integration tests."
        )

    base_url = _postgres_test_url(raw_url)
    schema = f"task_repository_test_{uuid.uuid4().hex}"
    admin_engine = create_engine(base_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    scoped_url = base_url.set(
        query={
            **base_url.query,
            "options": f"-csearch_path={schema}",
        }
    )
    repo = PostgreSQLTaskRepository(
        scoped_url.render_as_string(hide_password=False)
    )
    try:
        yield repo
    finally:
        repo.close()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _claim_analyzer(repository, task_id: str):
    claim = repository.claim_task(
        task_id,
        expected_stage=TaskStage.ANALYZER,
        worker_id="test-worker",
    )
    assert claim is not None
    return claim


def test_create_persist_filter_and_idempotent_submission(repository):
    first = repository.create_task(
        "  First task  ",
        "  First description  ",
        priority=4,
        submission_key="submission-1",
    )
    duplicate = repository.create_task(
        "Duplicate",
        "Should not be inserted",
        priority=99,
        submission_key="submission-1",
    )
    second = repository.create_task(
        "Second task",
        "Second description",
        priority=7,
    )

    assert first.task_id == duplicate.task_id
    assert first.thread_id == f"task-{first.task_id}"
    assert first.title == "First task"
    assert first.description == "First description"
    assert first.stage is TaskStage.ANALYZER
    assert first.status is TaskStatus.PENDING
    assert repository.get_task(first.task_id) == first

    pending = repository.list_pending_tasks(TaskStage.ANALYZER)
    assert [task.task_id for task in pending] == [
        second.task_id,
        first.task_id,
    ]
    assert repository.list_tasks(stage=TaskStage.DEVELOPER) == []


def test_complete_lifecycle_and_execution_token_validation(repository):
    task = repository.create_task("Lifecycle", "Run every stage")
    analyzer_claim = _claim_analyzer(repository, task.task_id)

    with pytest.raises(InvalidTaskTransitionError):
        repository.move_to_next_stage(
            task.task_id,
            "wrong token",
            execution_token="not-current",
        )
    with pytest.raises(InvalidTaskTransitionError):
        repository.record_execution_result(
            task.task_id,
            "unauthorized result",
            execution_token="not-current",
        )
    with pytest.raises(InvalidTaskTransitionError):
        repository.record_error(
            task.task_id,
            "unauthorized failure",
            execution_token="not-current",
        )

    developer_stage = repository.move_to_next_stage(
        task.task_id,
        "analysis result",
        execution_token=analyzer_claim.execution_token,
    )
    assert developer_stage.stage is TaskStage.DEVELOPER
    assert developer_stage.status is TaskStatus.PENDING
    assert developer_stage.analysis_result == "analysis result"
    assert developer_stage.awaiting_approval

    assert (
        repository.claim_task(
            task.task_id,
            expected_stage=TaskStage.DEVELOPER,
        )
        is None
    )

    approved = repository.approve_task(task.task_id)
    assert approved.approved_at is not None
    developer_claim = repository.claim_task(
        task.task_id,
        expected_stage=TaskStage.DEVELOPER,
        worker_id="developer-worker",
    )
    assert developer_claim is not None

    tester_stage = repository.move_to_next_stage(
        task.task_id,
        "development result",
        execution_token=developer_claim.execution_token,
    )
    assert tester_stage.stage is TaskStage.TESTER
    assert tester_stage.status is TaskStatus.PENDING
    assert tester_stage.development_result == "development result"

    tester_claim = repository.claim_task(
        task.task_id,
        expected_stage=TaskStage.TESTER,
        worker_id="tester-worker",
    )
    assert tester_claim is not None
    completed = repository.move_to_next_stage(
        task.task_id,
        "test result",
        execution_token=tester_claim.execution_token,
    )

    assert completed.stage is TaskStage.TESTER
    assert completed.status is TaskStatus.COMPLETED
    assert completed.test_result == "test result"
    assert completed.completed_at is not None


def test_update_task_status_preserves_completion_timestamp(repository):
    task = repository.create_task("Status", "Update status directly")
    completed = repository.update_task_status(
        task.task_id,
        TaskStatus.COMPLETED,
    )
    assert completed.status is TaskStatus.COMPLETED
    assert completed.completed_at is not None

    failed = repository.update_task_status(
        task.task_id,
        TaskStatus.FAILED,
        error_message="post-completion failure",
    )
    assert failed.status is TaskStatus.FAILED
    assert failed.completed_at == completed.completed_at


def test_failure_does_not_advance_and_retry_reuses_task(repository):
    task = repository.create_task("Failure", "Fail without advancing")
    claim = _claim_analyzer(repository, task.task_id)
    repository.record_execution_result(
        task.task_id,
        "partial analysis",
        execution_token=claim.execution_token,
    )
    failed = repository.record_error(
        task.task_id,
        "agent failed",
        execution_token=claim.execution_token,
    )

    assert failed.status is TaskStatus.FAILED
    assert failed.stage is TaskStage.ANALYZER
    assert failed.error_message == "agent failed"
    assert failed.analysis_result == "partial analysis"

    retried = repository.retry_task(task.task_id)
    assert retried.task_id == task.task_id
    assert retried.thread_id == task.thread_id
    assert retried.status is TaskStatus.PENDING
    assert retried.stage is TaskStage.ANALYZER
    assert retried.retry_count == 1
    assert retried.analysis_result == "partial analysis"
    assert retried.error_message is None
    assert len(repository.list_tasks()) == 1


def test_rejected_analysis_retries_from_analyzer(repository):
    task = repository.create_task("Rejected", "Reject the analysis")
    claim = _claim_analyzer(repository, task.task_id)
    repository.move_to_next_stage(
        task.task_id,
        "review me",
        execution_token=claim.execution_token,
    )
    rejected = repository.fail_awaiting_review(
        task.task_id,
        "Analysis rejected by human.",
    )

    assert rejected.status is TaskStatus.FAILED
    assert rejected.stage is TaskStage.ANALYZER
    retried = repository.retry_task(task.task_id)
    assert retried.stage is TaskStage.ANALYZER
    assert retried.status is TaskStatus.PENDING


def test_recovery_requeues_running_tasks_and_invalidates_token(repository):
    task = repository.create_task("Interrupted", "Recover this task")
    claim = _claim_analyzer(repository, task.task_id)

    recovered = repository.recover_interrupted_tasks()
    assert [item.task_id for item in recovered] == [task.task_id]
    assert recovered[0].status is TaskStatus.PENDING
    assert recovered[0].recovery_count == 1
    assert recovered[0].error_message is not None

    with pytest.raises(InvalidTaskTransitionError):
        repository.move_to_next_stage(
            task.task_id,
            "stale result",
            execution_token=claim.execution_token,
        )


def test_concurrent_workers_claim_exactly_one_task(repository):
    task = repository.create_task("Concurrency", "Claim once")
    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def claim(worker_index: int):
        barrier.wait()
        return repository.claim_task(
            task.task_id,
            expected_stage=TaskStage.ANALYZER,
            worker_id=f"worker-{worker_index}",
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        claims = list(executor.map(claim, range(worker_count)))

    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert repository.get_task(task.task_id).status is TaskStatus.RUNNING


def test_concurrent_transition_allows_one_winner(repository):
    task = repository.create_task("Transition", "Advance once")
    claim = _claim_analyzer(repository, task.task_id)
    barrier = threading.Barrier(2)

    def advance():
        barrier.wait()
        try:
            repository.move_to_next_stage(
                task.task_id,
                "winner",
                execution_token=claim.execution_token,
            )
        except InvalidTaskTransitionError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: advance(), range(2)))

    assert outcomes.count(True) == 1
    stored = repository.get_task(task.task_id)
    assert stored.stage is TaskStage.DEVELOPER
    assert stored.status is TaskStatus.PENDING
    assert stored.analysis_result == "winner"


def test_concurrent_duplicate_submission_returns_same_task(repository):
    barrier = threading.Barrier(4)

    def submit(_index: int):
        barrier.wait()
        return repository.create_task(
            "Idempotent",
            "Concurrent submission",
            submission_key="shared-submission-key",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = list(executor.map(submit, range(4)))

    assert len({task.task_id for task in tasks}) == 1
    assert len(repository.list_tasks()) == 1


def test_existing_sqlite_schema_remains_readable(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE workflow_tasks (
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
        """
    )
    connection.execute(
        """
        INSERT INTO workflow_tasks (
            task_id,
            title,
            description,
            stage,
            status,
            priority,
            thread_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "legacy-task",
            "Legacy",
            "Existing data",
            "ANALYZER",
            "PENDING",
            0,
            "task-legacy-task",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.commit()
    connection.close()

    repo = SQLiteTaskRepository(db_path)
    try:
        task = repo.get_task("legacy-task")
        assert task.title == "Legacy"
        new_task = repo.create_task("New", "Compatible")
        assert repo.get_task(new_task.task_id) == new_task
        assert repo.get_task("legacy-task") == task
        with repo.engine.connect() as connection:
            index_names = {
                row[0]
                for row in connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            }
        assert "idx_workflow_tasks_queue" in index_names
        assert "idx_workflow_tasks_thread" in index_names
    finally:
        repo.close()


def test_repository_factory_validates_backend_configuration(tmp_path):
    sqlite_repo = create_task_repository(
        backend="sqlite",
        sqlite_db_path=tmp_path / "factory.sqlite3",
    )
    try:
        assert isinstance(sqlite_repo, SQLiteTaskRepository)
    finally:
        sqlite_repo.close()

    with pytest.raises(RuntimeError, match="TASK_DATABASE_URL"):
        create_task_repository(
            backend="postgres",
            sqlite_db_path=tmp_path / "unused.sqlite3",
        )

    with pytest.raises(ValueError, match="either 'sqlite' or 'postgres'"):
        create_task_repository(
            backend="oracle",
            sqlite_db_path=tmp_path / "unused.sqlite3",
        )


def test_repository_factory_reads_backend_environment(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("TASK_REPOSITORY_BACKEND", "sqlite")
    repo = create_task_repository(
        sqlite_db_path=tmp_path / "environment.sqlite3",
    )
    try:
        assert isinstance(repo, SQLiteTaskRepository)
    finally:
        repo.close()


def test_shared_schema_compiles_for_postgresql():
    dialect = postgresql.dialect()
    create_sql = str(CreateTable(workflow_tasks).compile(dialect=dialect))
    index_sql = [
        str(CreateIndex(index).compile(dialect=dialect))
        for index in workflow_tasks.indexes
    ]

    assert "workflow_tasks" in create_sql
    assert "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')" in (
        create_sql
    )
    assert any(
        "idx_workflow_tasks_queue" in statement for statement in index_sql
    )


def test_existing_workflow_runs_with_new_repository(monkeypatch, tmp_path):
    class Analyzer:
        def analyze(self, story: str) -> str:
            return f"analysis:{story}"

    class Developer:
        def develop(self, analysis: str) -> str:
            return f"development:{analysis}"

    class Tester:
        def test(
            self,
            story: str,
            development_result: str,
            test_analysis: str | None = None,
        ) -> str:
            return f"test:{development_result}"

    import service.task_service as task_service

    monkeypatch.setattr(task_service, "TASK_REPOSITORY_BACKEND", "sqlite")
    monkeypatch.setattr(task_service, "TASK_DATABASE_URL", None)

    with TaskWorkflowRuntime.create(
        db_path=tmp_path / "workflow.sqlite3",
        analyzer=Analyzer(),
        developer=Developer(),
        tester=Tester(),
    ) as runtime:
        task = runtime.service.create_task("Workflow", "Run with fakes")
        runtime.service.run_task(task.task_id)
        waiting = runtime.repository.get_task(task.task_id)
        assert waiting.stage is TaskStage.DEVELOPER
        assert waiting.awaiting_approval

        runtime.service.approve_task(task.task_id)
        completed = runtime.repository.get_task(task.task_id)
        assert completed.stage is TaskStage.TESTER
        assert completed.status is TaskStatus.COMPLETED
        assert completed.thread_id == task.thread_id
        assert completed.analysis_result == "analysis:Run with fakes"
        assert completed.development_result == (
            "development:analysis:Run with fakes"
        )
        assert completed.test_result == (
            "test:development:analysis:Run with fakes"
        )
