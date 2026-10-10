from pathlib import Path

from openai_codex import Codex, Sandbox


class DeveloperAgent:

    def __init__(
        self,
        project_path: str,
        architect_file: str,
        agent_file: str,
    ):
        self.project_path = Path(project_path).resolve()
        self.architect_file = Path(architect_file).resolve()
        self.agent_file = Path(agent_file).resolve()

    def run(self, task: str) -> str:

        self._validate()

        prompt = self._build_prompt(task)

        with Codex() as codex:

            thread = codex.thread_start(
                cwd=str(self.project_path),
                sandbox=Sandbox.workspace_write,
            )

            result = thread.run(prompt)

            return result.final_response

    def _validate(self):

        if not self.project_path.is_dir():
            raise ValueError(
                f"Project directory does not exist: {self.project_path}"
            )

        if not self.architect_file.is_file():
            raise ValueError(
                f"Architect file does not exist: {self.architect_file}"
            )

        if not self.agent_file.is_file():
            raise ValueError(
                f"Agent instructions file does not exist: {self.agent_file}"
            )

    def _build_prompt(self, task: str) -> str:

        architect = self.architect_file.read_text(
            encoding="utf-8"
        )

        agent_instructions = self.agent_file.read_text(
            encoding="utf-8"
        )

        return f"""
You are the Developer Agent.

You are working on this project:

{self.project_path}

You MUST follow the following architecture document:

================ ARCHITECT.md ================
{architect}
================ END ARCHITECT.md =============


You MUST follow these agent instructions:

================ agent.md ================
{agent_instructions}
================ END agent.md ===============


Your task is:

================ TASK ================
{task}
================ END TASK =============


Instructions:

1. Inspect the existing project before making changes.
2. Understand the existing implementation and architecture.
3. Do not invent business logic when the existing code does not provide enough information.
4. Make the smallest reasonable changes required by the task.
5. Do not modify unrelated code.
6. Verify your implementation using the appropriate project commands.
7. At the end, return a report with:

   ## Summary
   What was implemented.

   ## Files Changed
   List all files that were created or modified.

   ## Implementation Details
   Explain the important implementation decisions.

   ## Verification
   Explain what was executed to verify the implementation.

   ## Risks / Notes
   Mention unresolved issues, assumptions, or risks.

   ## Final Result
   State whether the task was completed successfully.
"""