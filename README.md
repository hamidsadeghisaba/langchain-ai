# LangChain multi-agent workflow

This project persists the Analyzer, Developer, and Tester workflow with
LangGraph checkpoints and a SQLAlchemy Core task repository.

## Install and run

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Run the repository tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

SQLite tests run by default. To execute the PostgreSQL integration cases, point
`TASK_TEST_POSTGRES_URL` at a disposable PostgreSQL database whose user can
create schemas:

```powershell
$env:TASK_TEST_POSTGRES_URL = "postgresql+psycopg://user:password@localhost:5432/test"
.\.venv\Scripts\python.exe -m pytest tests -q
```

Each PostgreSQL test run creates and removes a uniquely named schema. Without
this variable, the PostgreSQL cases are reported as skipped.

## Task repository configuration

`TASK_REPOSITORY_BACKEND` selects task metadata storage:

- `sqlite` (default) uses `WORKFLOW_DB_PATH`.
- `postgres` uses `TASK_DATABASE_URL`.

SQLite example:

```powershell
$env:TASK_REPOSITORY_BACKEND = "sqlite"
$env:WORKFLOW_DB_PATH = "E:\path\to\workflow.sqlite3"
```

PostgreSQL example:

```powershell
$env:TASK_REPOSITORY_BACKEND = "postgres"
$env:TASK_DATABASE_URL = "postgresql+psycopg://user:password@localhost:5432/workflow"
$env:TASK_DB_POOL_SIZE = "5"
$env:TASK_DB_MAX_OVERFLOW = "10"
```

See [.env.example](.env.example) for all repository settings. The application
reads process environment variables; the example file is not loaded
automatically.

LangGraph continues to use the SQLite checkpointer because changing workflow
persistence is outside this repository refactor. When PostgreSQL is selected,
task metadata is stored in PostgreSQL while LangGraph checkpoints remain in
`WORKFLOW_DB_PATH`.

## Schema compatibility

The SQLAlchemy Core `workflow_tasks` table preserves the existing SQLite column
names, constraints, defaults, and indexes. Startup creates a missing table or
index without deleting or replacing an existing database. No data migration is
required for existing SQLite databases. A PostgreSQL database receives the
shared schema on first startup.

Concurrent task claims use an atomic conditional `UPDATE` from `PENDING` to
`RUNNING`. Execution-token checks guard results, errors, and stage transitions.
