from pathlib import Path

from openai_codex import Codex, Sandbox
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent

llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key="sk-de578784f6cb4fb0b879f507ce87fab8",
    base_url="https://api.deepseek.com/v1",
)

PROJECT_ROOT = Path(".").resolve()

@tool
def list_files() -> str:
    """List files in the project directory."""
    files = []

    for path in PROJECT_ROOT.rglob("*"):
        if path.is_file():
            files.append(str(path.relative_to(PROJECT_ROOT)))

    return "\n".join(files)

@tool
def read_file(file_path: str) -> str:
    """Read a text file from the project directory."""

    path = (PROJECT_ROOT / file_path).resolve()

    # Prevent reading files outside the project
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        return "Access denied."

    if not path.is_file():
        return f"File not found: {file_path}"

    return path.read_text(encoding="utf-8")

@tool
def run_codex(task: str) -> str:
    """
    Ask the Codex coding agent to perform a software development task
    in the current project.
    """

    try:
        with Codex() as codex:
            thread = codex.thread_start(
                cwd=str(PROJECT_ROOT),
                sandbox=Sandbox.workspace_write,
            )

            result = thread.run(task)

            return result.final_response

    except Exception as e:
        return f"Codex execution failed: {e}"

agent = create_agent(
    model=llm,
    tools=[
        list_files,
        read_file,
        run_codex,
    ],
    system_prompt="""
You are a software development assistant.

Use the available tools to inspect the project.

If the user asks you to modify or implement code,
use the run_codex tool.

Do not invent information about the project.
""",
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "Inspect this project and tell me what files it contains.",
            }
        ]
    }
)

print(result["messages"][-1].content)