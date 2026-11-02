Refactor the existing `PersistantTaskRepository` to use **SQLAlchemy Core** and support both SQLite and PostgreSQL.

Requirements:

1. Create a shared `PersistentTaskRepository` containing common task and workflow operations.
2. Create separate `SQLiteTaskRepository` and `PostgreSQLTaskRepository` implementations for database-specific configuration and behavior.
3. Define the `workflow_tasks` table using SQLAlchemy Core in a shared schema module.
4. Use SQLAlchemy transactions and connection pooling.
5. Preserve all existing methods, signatures, return types, and business rules.
6. Preserve atomic task claiming, execution-token validation, human approval, retry handling, interrupted-task recovery, and stable `thread_id`.
7. Ensure concurrent workers cannot claim or execute the same task simultaneously. Implement database-appropriate atomic operations.
8. Select the database backend through environment configuration (`TASK_REPOSITORY_BACKEND=sqlite|postgres`).
9. Update dependencies, `.env.example`, and documentation.
10. Add tests for both backends, especially transaction safety, concurrency, and task state transitions.

Important:

- Use SQLAlchemy Core, NOT ORM.
- Do not change the LangGraph workflow, Codex SDK, DeepSeek integration, or agent implementations.
- Do not introduce unnecessary architectural changes.
- Keep existing SQLite data compatible; do not delete or overwrite existing databases.
- Inspect the project before modifying code.
- Run existing and new tests, and report changed files, test results, and any migration requirements.
