from pathlib import Path

from langchain_core.tools import tool
from openai_codex import Codex, Sandbox

from config import (
    PROJECT_PATH,
    ARCHITECT_FILE,
    AGENT_FILE,
)


@tool
def developer_agent(task: str) -> str:
    """
    Execute a software development task using the Codex coding agent.

    Codex works inside the configured project directory,
    follows Architect.md and agent.md,
    implements the task and returns an implementation report.
    """

    if not PROJECT_PATH.is_dir():
        return f"Project directory does not exist: {PROJECT_PATH}"

    if not ARCHITECT_FILE.is_file():
        return f"Missing architecture file: {ARCHITECT_FILE}"

    if not AGENT_FILE.is_file():
        return f"Missing agent instructions file: {AGENT_FILE}"

    prompt = f"""
You are the Developer Agent.

Working directory:

{PROJECT_PATH}

Before doing anything:

1. Read:
   docs/Architect.md

2. Read:
   docs/agent.md

3. Inspect the existing project and understand the current implementation.

Task:

{task}

Rules:

- Follow Architect.md.
- Follow agent.md.
- Inspect existing code before modifying it.
- Make the smallest reasonable change.
- Do not modify unrelated code.
- Do not invent business logic.
- Verify your implementation.

At the end return a report:

## Summary

## Files Changed

## Implementation Details

## Verification

## Risks / Notes

## Final Result
"""

    try:

        with Codex() as codex:

            thread = codex.thread_start(
                cwd=str(PROJECT_PATH),
                sandbox=Sandbox.workspace_write,
            )

            result = thread.run(prompt)

            return result.final_response

    except Exception as e:

        return (
            f"Developer Agent failed: "
            f"{type(e).__name__}: {e}"
        )