from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from analyzerAgent import AnalyzerAgent
from config import WORKFLOW_DB_PATH
from developerAgent import DeveloperAgent
from task_queue import (
    SQLiteTaskRepository,
    Task,
    TaskStage,
    TaskStatus,
)
from testAgent import TesterAgent
from workflow import AgentState, build_graph, initial_state


class TaskAwaitingApprovalError(RuntimeError):
    pass


class SQLiteCheckpointStore:
    """Own the long-lived SQLite connection used by LangGraph."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.db_path,
            timeout=5.0,
            check_same_thread=False,
        )
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.saver = SqliteSaver(self.connection)
        self.saver.setup()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "SQLiteCheckpointStore":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


class TaskWorkflowService:
    """Coordinates queue rows, LangGraph checkpoints, and stage execution."""

    def __init__(
        self,
        repository: SQLiteTaskRepository,
        graph,
    ):
        self.repository = repository
        self.graph = graph

    @staticmethod
    def thread_config(task: Task) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": task.thread_id}}

    def create_task(
        self,
        title: str,
        description: str,
        *,
        priority: int = 0,
        submission_key: str | None = None,
    ) -> Task:
        return self.repository.create_task(
            title=title,
            description=description,
            priority=priority,
            submission_key=submission_key,
        )

    def run_task(self, task_id: str) -> AgentState:
        task = self.repository.get_task(task_id)
        if task.status is TaskStatus.COMPLETED:
            return initial_state(task)
        if task.status is TaskStatus.RUNNING:
            raise RuntimeError("This task is already running.")
        if task.status is TaskStatus.FAILED:
            raise RuntimeError("Retry the failed task before running it again.")
        if task.awaiting_approval:
            raise TaskAwaitingApprovalError(
                "The Developer stage is waiting for human approval."
            )

        # If the process stopped after approval was persisted but before the
        # graph consumed the interrupt, resume that checkpoint instead of
        # starting a competing run for the same Developer stage.
        if task.stage is TaskStage.DEVELOPER and task.approved_at is not None:
            snapshot = self.graph.get_state(self.thread_config(task))
            if snapshot.interrupts:
                return self.graph.invoke(
                    Command(resume="approve"),
                    self.thread_config(task),
                )

        return self.graph.invoke(
            initial_state(task),
            self.thread_config(task),
        )

    def approve_task(self, task_id: str) -> AgentState:
        task = self.repository.get_task(task_id)
        if not task.awaiting_approval:
            raise RuntimeError(
                "Only a pending Developer-stage task awaiting review can be approved."
            )

        snapshot = self.graph.get_state(self.thread_config(task))
        if snapshot.interrupts:
            return self.graph.invoke(
                Command(resume="approve"),
                self.thread_config(task),
            )

        # The task row can reach the review gate just before LangGraph writes its
        # checkpoint. If a crash lands in that gap, use the durable analysis in
        # the task row and start directly at the approved Developer stage.
        self.repository.approve_task(task_id)
        approved = self.repository.get_task(task_id)
        return self.graph.invoke(
            initial_state(approved),
            self.thread_config(approved),
        )

    def reject_task(self, task_id: str) -> None:
        task = self.repository.get_task(task_id)
        if not task.awaiting_approval:
            raise RuntimeError(
                "Only a pending Developer-stage task awaiting review can be rejected."
            )

        snapshot = self.graph.get_state(self.thread_config(task))
        if not snapshot.interrupts:
            self.repository.fail_awaiting_review(
                task_id,
                "Analysis rejected by human.",
            )
            return

        try:
            self.graph.invoke(
                Command(resume="reject"),
                self.thread_config(task),
            )
        except ValueError as error:
            failed = self.repository.get_task(task_id)
            if (
                failed.status is TaskStatus.FAILED
                and failed.stage is TaskStage.ANALYZER
                and "rejected" in (failed.error_message or "").lower()
            ):
                return
            raise error

    def retry_task(self, task_id: str, *, run: bool = False) -> Task | AgentState:
        task = self.repository.retry_task(task_id)
        if run:
            return self.run_task(task.task_id)
        return task

    def run_next(self, stage: TaskStage) -> AgentState:
        for task in self.repository.list_pending_tasks(stage):
            if task.stage is TaskStage.DEVELOPER and task.approved_at is None:
                continue
            return self.run_task(task.task_id)
        raise LookupError(f"No runnable task in the {stage.value} queue.")


class TaskWorkflowRuntime:
    """Application-owned resources for Streamlit and the CLI."""

    def __init__(
        self,
        *,
        repository: SQLiteTaskRepository,
        graph,
        checkpoint_store: SQLiteCheckpointStore,
    ):
        self.repository = repository
        self.graph = graph
        self.checkpoint_store = checkpoint_store
        self.service = TaskWorkflowService(repository, graph)

    @classmethod
    def create(
        cls,
        *,
        db_path: str | Path = WORKFLOW_DB_PATH,
        analyzer=None,
        developer=None,
        tester=None,
    ) -> "TaskWorkflowRuntime":
        repository = SQLiteTaskRepository(db_path)
        checkpoint_store = SQLiteCheckpointStore(db_path)
        graph = build_graph(
            repository=repository,
            analyzer=analyzer or AnalyzerAgent(),
            developer=developer or DeveloperAgent(),
            tester=tester or TesterAgent(),
            checkpointer=checkpoint_store.saver,
        )
        runtime = cls(
            repository=repository,
            graph=graph,
            checkpoint_store=checkpoint_store,
        )
        repository.recover_interrupted_tasks()
        return runtime

    def close(self) -> None:
        self.checkpoint_store.close()

    def __enter__(self) -> "TaskWorkflowRuntime":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
