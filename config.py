from pathlib import Path

# PATHS
# PROJECT_REPO
PROJECT_PATH :Path = Path(r"E:\project\dotin\PTS")
TEST_PROJECT_PATH :str = r"E:\project\dotin\PTS\psp-settle-integtest"
MODULE_NAME : str = "settle"
# MD Files
CWD = Path(r"./")
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