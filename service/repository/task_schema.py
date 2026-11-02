from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
)


metadata = MetaData()

# The column names, nullability, uniqueness, and defaults intentionally match
# the existing SQLite schema so existing task databases remain compatible.
workflow_tasks = Table(
    "workflow_tasks",
    metadata,
    Column("task_id", Text, primary_key=True),
    Column("submission_key", Text, unique=True),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("stage", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("priority", Integer, nullable=False, server_default="0"),
    Column("thread_id", Text, nullable=False, unique=True),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("error_message", Text),
    Column("approved_at", Text),
    Column("retry_count", Integer, nullable=False, server_default="0"),
    Column("recovery_count", Integer, nullable=False, server_default="0"),
    Column(
        "analysis_result",
        Text,
        nullable=False,
        server_default="",
    ),
    Column(
        "development_result",
        Text,
        nullable=False,
        server_default="",
    ),
    Column("test_result", Text, nullable=False, server_default=""),
    Column("completed_at", Text),
    Column("execution_token", Text),
    Column("worker_id", Text),
    CheckConstraint("length(trim(title)) > 0", name="ck_workflow_tasks_title"),
    CheckConstraint(
        "length(trim(description)) > 0",
        name="ck_workflow_tasks_description",
    ),
    CheckConstraint(
        "stage IN ('ANALYZER', 'DEVELOPER', 'TESTER')",
        name="ck_workflow_tasks_stage",
    ),
    CheckConstraint(
        "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
        name="ck_workflow_tasks_status",
    ),
)

Index(
    "idx_workflow_tasks_queue",
    workflow_tasks.c.stage,
    workflow_tasks.c.status,
    workflow_tasks.c.priority.desc(),
    workflow_tasks.c.created_at.asc(),
)
Index(
    "idx_workflow_tasks_thread",
    workflow_tasks.c.thread_id,
)
