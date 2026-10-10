from pathlib import Path
from config import (
    ARCHITECT_MD,
    DEVELOPER_AGENT_MD,
    GRAPHIPY_JSON,
    GRAPHIPY_PRODUCT,
    PROJECT_PATH,
    PUBLIC_MODEL,
    PUBLIC_PROVIDER,
    PYTHON_CMD
)

from myCodexAgent import (
    MyCodexAgent,
    CodexAgentConfig,
    GraphifyServerConfig,
)

class DeveloperAgent:

    def __init__(self):

        self.codex = MyCodexAgent(
            CodexAgentConfig(
                repo=str(PROJECT_PATH),
                
                graphify_servers=(
                    GraphifyServerConfig(
                        name=GRAPHIPY_PRODUCT,
                        graph_path=( PROJECT_PATH / GRAPHIPY_JSON ),
                        python=PYTHON_CMD,
                    ),
                ),
                model=PUBLIC_MODEL,
                model_provider=PUBLIC_PROVIDER,
            )
        )

    def develop(self, analysis: str) -> str:

        if not analysis or not analysis.strip():
            raise ValueError("ُnalysis cannot be empty")

        developer_md = Path( DEVELOPER_AGENT_MD ).read_text(encoding="utf-8")

        architect_md = Path( ARCHITECT_MD ).read_text(encoding="utf-8")

        prompt = f"""
==================================================
DEVELOPER INSTRUCTIONS
==================================================

{developer_md}

==================================================
ARCHITECTURE
==================================================

{architect_md}

==================================================
TASK
==================================================

{analysis}

=================================================="""
# OUTPUT
# ==================================================
# """

        return self.codex.run(prompt)


if __name__ == "__main__":
    agent = DeveloperAgent()

    result = agent.develop(
        analysis="Create a simple DTO class in Charisma-datamodel."
    )

    print("\n=== RESULT ===")
    print(result)