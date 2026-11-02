import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# PATHS
# PROJECT_REPO
PROJECT_PATH :Path = Path(r"E:\project\dotin\PTS")
TEST_PROJECT_PATH :Path = Path(r"E:\project\dotin\PTS\psp-settle-integtest")
MODULE_NAME : str = "settle"
# MD Files
CWD = BASE_DIR
ARCHITECT_MD = (CWD / "docs/md" / MODULE_NAME / "ARCHITECTURE.md")
DEVELOPER_AGENT_MD = CWD / "docs/md" / MODULE_NAME / "DEVELOPER_AGENTS.md"
ANALYZER_AGENT_MD = CWD / "docs/md" / MODULE_NAME / "ANALYZER_AGENTS.md"
TEST_ANALYZER_AGENT_MD = CWD / "docs/md" / MODULE_NAME / "TEST_ANALYZER_AGENTS.md"
TESTER_AGENT_MD = CWD / "docs/md" / MODULE_NAME / "TESTER_AGENTS.md"
# GRAPHIPY
GRAPHIPY_JSON = "graphify-out/graph.json"
GRAPHIPY_PRODUCT = "graphify-production"
GRAPHIPY_TEST = "graphify-test"
# PYTHON
PYTHON_HOME = Path(r"C:\Users\h.sadeghii\AppData\Local\Programs");
PYTHON_CMD = PYTHON_HOME / "Python/Python314/python.exe";
# codex
CODEX_CMD = (
        r"E:\project\ai\langchain-poc\.venv"
        r"\Lib\site-packages\codex_cli_bin\bin\codex.exe"
    )

# LLM
DEEPSEEK_PROVIDER = "deepseek"
DEEPSEEK_MODEL = "deepseek-v4-flash"

PUBLIC_PROVIDER = DEEPSEEK_PROVIDER
PUBLIC_MODEL = DEEPSEEK_MODEL

# Persistent workflow data. The task table and LangGraph checkpoints share one
# SQLite file but remain separate schemas managed by their respective owners.
WORKFLOW_DATA_DIR = Path(
    os.environ.get("WORKFLOW_DATA_DIR", BASE_DIR / "data")
)
WORKFLOW_DB_PATH = Path(
    os.environ.get("WORKFLOW_DB_PATH", WORKFLOW_DATA_DIR / "workflow.sqlite3")
)

# LangGraph checkpoints use their own backend selection and are independent
# from task metadata storage.
CHECKPOINT_BACKEND = os.environ.get(
    "CHECKPOINT_BACKEND",
    "sqlite",
).strip().lower()
CHECKPOINT_SQLITE_PATH = Path(
    os.environ.get("CHECKPOINT_SQLITE_PATH", WORKFLOW_DB_PATH)
)
CHECKPOINT_POSTGRES_URL = os.environ.get("CHECKPOINT_POSTGRES_URL")

# Task metadata can use SQLite or PostgreSQL. When PostgreSQL is selected,
# WORKFLOW_DB_PATH remains the task repository's SQLite default.
TASK_REPOSITORY_BACKEND = os.environ.get(
    "TASK_REPOSITORY_BACKEND",
    "sqlite",
).strip().lower()
TASK_DATABASE_URL = os.environ.get("TASK_DATABASE_URL")
