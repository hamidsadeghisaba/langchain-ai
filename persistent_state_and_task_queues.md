# Task: Implement Persistent State and Task Queues in the Existing Multi-Agent Workflow

## 1. Project context

Project directory:

`E:\project\ai\langchain-poc`

The project uses:

- Python
- LangChain
- LangGraph
- OpenAI Codex SDK
- DeepSeek as the LLM provider
- Streamlit

The application already contains three agents:

1. Analyzer
2. Developer
3. Tester

The current workflow is:

Analyzer → Developer → Tester

Codex SDK is used as the agent execution mechanism, while DeepSeek provides the LLM.

Do not confuse the two roles. Do not introduce a separate DeepSeek agent or replace the existing Codex SDK integration.

## 2. Current environment

The application runs using:

`.venv/Scripts/python.exe`

The environment contains:

- `langgraph==1.2.12`
- `langgraph-checkpoint==4.3.1`
- `langgraph-checkpoint-sqlite==3.1.2`

SQLite checkpoint persistence has been successfully tested in `test_sqlite_checkpoint.py`.

The test confirmed that LangGraph state can be persisted to a database file and restored after reopening the database.

Reuse the existing dependencies. Do not downgrade or unnecessarily upgrade packages.

## 3. First inspect the existing implementation

Before modifying files:

1. Inspect the project structure and current Git changes.
2. Identify the State definition and LangGraph graph construction.
3. Locate the Analyzer, Developer, and Tester implementations.
4. Identify how Codex SDK invokes the agents and how DeepSeek is configured as the LLM.
5. Inspect the Streamlit interface and its execution model.
6. Inspect the existing checkpoint test and dependency files.

Preserve the current working agent implementations, DeepSeek configuration, Codex SDK integration, and workflow behavior.

Do not rewrite the application from scratch.

## 4. Objective A: Persistent LangGraph state

Integrate the official SQLite checkpointer into the existing LangGraph workflow.

Requirements:

- Persist checkpoints in a database file.
- Assign a stable, unique `thread_id` to every task.
- Ensure separate tasks have separate checkpoint histories.
- Reuse the appropriate thread when resuming a task.
- Ensure state survives application restarts.
- Manage connections and checkpointer lifecycles correctly.
- Avoid losing access to the checkpointer during Streamlit reruns.
- Do not assume checkpoint persistence automatically provides queue management.

Use the installed version-compatible SQLite checkpointer API.

## 5. Objective B: Three persistent task queues

Implement three logical queues:

- Analyzer Queue
- Developer Queue
- Tester Queue

These queues must persist across application restarts.

Prefer one shared task table with a `stage` column and suitable indexes, rather than three separate physical queue tables.

Each task should include at least:

- `task_id`: unique task identifier
- `title`: task title
- `description`: task requirements
- `stage`: ANALYZER, DEVELOPER, or TESTER
- `status`: PENDING, RUNNING, COMPLETED, or FAILED
- `priority`: task priority
- `thread_id`: associated LangGraph thread identifier
- `created_at`
- `updated_at`
- `error_message`

Adjust the schema where necessary to fit the existing application.

Implement repository methods to:

- Create a task.
- Retrieve a task by ID.
- List pending tasks for a stage.
- Claim a task for execution.
- Update task status.
- Move a task to the next stage.
- Record execution results and errors.
- Retry a failed task without creating a duplicate task.
- Recover tasks left in RUNNING after an interruption.

Use parameterized SQL and appropriate indexes.

Keep task metadata persistence conceptually separate from LangGraph checkpoint persistence.

## 6. Objective C: Integrate queues with the existing workflow

Implement this lifecycle:

1. A new task is persisted and placed in the Analyzer queue.
2. The existing Analyzer agent executes through the current Codex SDK and DeepSeek integration.
3. After successful analysis, the task enters the Developer queue.
4. The existing Developer agent executes through the same existing integration.
5. After successful development, the task enters the Tester queue.
6. The existing Tester agent executes through the same existing integration.
7. After successful testing, the task is marked COMPLETED.

Important requirements:

- Preserve the existing agent implementations and responsibilities.
- Do not create duplicate agent implementations.
- Do not bypass the current Codex SDK execution mechanism.
- Do not replace DeepSeek with another LLM.
- Do not advance a task when the current stage fails.
- Persist intermediate results needed by subsequent stages.
- Record errors and provide a safe retry mechanism.
- Prevent accidental duplicate submissions and concurrent processing where practical.
- Recover interrupted tasks without silently losing their state.
- Avoid automatic infinite retry loops.
- Keep task stage and execution state consistent.

Inspect the current graph before choosing the transition mechanism. Integrate queue management with the existing workflow instead of duplicating orchestration logic.

## 7. Objective D: Streamlit integration

Integrate the queues into the existing Streamlit application.

Provide:

- Task submission.
- Analyzer queue view.
- Developer queue view.
- Tester queue view.
- Task details and current status.
- Intermediate results where appropriate.
- Error details for failed tasks.
- A retry action for failed tasks.

Ensure that Streamlit reruns do not accidentally create duplicate tasks or trigger unintended repeated executions.

Preserve the existing interface where practical.

Do not introduce an external message broker or a separately installed database server. SQLite is sufficient for this implementation.

## 8. Objective E: Tests

Add or update tests covering:

1. Task creation and persistence.
2. Correct filtering of the three queues.
3. Correct Analyzer → Developer transition.
4. Correct Developer → Tester transition.
5. Successful completion after testing.
6. Failure without advancing to the next stage.
7. Checkpoint persistence after reopening the database.
8. Isolation between different task threads.
9. Retrying without creating a duplicate task.
10. Recovery of interrupted tasks.
11. Prevention of duplicate processing where the implementation claims to support it.

Use deterministic test doubles or mocked agents. Tests must not invoke real LLM requests or run real Codex coding tasks.

Run tests using the project's virtual environment.

## 9. Implementation constraints

- Work within the existing project.
- Preserve unrelated user changes.
- Do not delete existing functionality unnecessarily.
- Do not introduce unnecessary dependencies.
- Do not make assumptions about undocumented project behavior; inspect the source code.
- Do not hardcode secrets or credentials.
- Do not claim tests passed unless they were actually executed.
- Keep the design extensible so Oracle or another production database could replace SQLite later.

## 10. Execution plan

Proceed through these steps:

1. Inspect and understand the current code.
2. Identify the smallest reasonable implementation plan.
3. Implement persistent task metadata and queue queries.
4. Integrate SQLite checkpoint persistence.
5. Integrate queue transitions with the existing three-agent workflow.
6. Update Streamlit.
7. Add and execute tests.
8. Review persistence, failures, concurrency, and recovery.

Implement the changes in the repository. Do not stop after producing a plan.

## 11. Final report

Report:

- Existing architecture discovered.
- Files created or modified.
- Database schema and database location.
- How Codex SDK and DeepSeek remain integrated.
- How task IDs and thread IDs are associated.
- How each queue works.
- How retries and crash recovery work.
- Tests executed and their actual results.
- Remaining limitations.
- Exact commands to run the application and tests using `.venv/Scripts/python.exe`.