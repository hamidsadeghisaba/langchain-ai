from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
