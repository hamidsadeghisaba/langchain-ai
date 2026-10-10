from pathlib import Path

from config import ANALYZER_AGENT_MD, ARCHITECT_MD, GRAPHIPY_JSON, GRAPHIPY_PRODUCT, PROJECT_PATH, PUBLIC_MODEL, PUBLIC_PROVIDER, PYTHON_CMD
from myCodexAgent import (
    MyCodexAgent,
    CodexAgentConfig,
    GraphifyServerConfig
)

class AnalyzerAgent:

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

    def analyze(self, story: str) -> str:

        if not story or not story.strip():
            raise ValueError("Story cannot be empty")

        agent_md = Path( r"E:\project\ai\langchain-poc\docs\md\settle\ANALYZER_AGENTS.md" ).read_text(encoding="utf-8")

        architect_md = Path( r"E:\project\ai\langchain-poc\docs\md\settle\ARCHITECTURE.md" ).read_text(encoding="utf-8")

        prompt = f"""
You are a Analyzer Agent.

Your responsibility is to analyze the requested software change
and produce a technical analysis for the Developer Agent.

==================================================
ANALYZER INSTRUCTIONS
==================================================

{agent_md}

==================================================
ARCHITECTURE
==================================================

{architect_md}

==================================================
MANDATORY ANALYSIS WORKFLOW
==================================================

Follow this order strictly.

1. FIRST use the Graphify MCP server:

   graphify-production

2. Call the Graphify MCP tools to understand the architecture
   and locate relevant components.

3. Graphify analysis MUST happen before source-code inspection.

4. After Graphify analysis, inspect the relevant source code.

5. Compare Graphify information with the actual source code.

6. Identify existing implementation patterns.

7. Produce the final technical analysis.

==================================================
RESTRICTIONS
==================================================

You are an ANALYZER.

Do NOT:

- modify source code
- create files
- delete files
- implement the story
- create commits
- change configuration

You may read repository files and inspect source code.

==================================================
TASK
==================================================

{story}

==================================================
OUTPUT
==================================================

Produce a structured technical analysis containing:

# Requirement

What needs to be implemented.

# Affected Modules

Relevant modules and why they are affected.

# Jobs

Relevant jobs, including:

- job name
- responsibility
- trigger
- input
- output

# Database / Tables

Relevant tables, including:

- table name
- purpose
- relevant columns
- relationships

# Classes and Services

Relevant classes/services, including:

- fully qualified class name
- responsibility
- relevant methods
- reason for involvement

# Existing Flow

Describe the current execution flow.

# Required Changes

Describe exactly what the Developer Agent needs to change.

Do not provide implementation code.

# Existing Patterns

Identify existing classes or implementations that should
be used as the implementation reference.

# Integration Points

Describe interactions with:

- other modules
- database
- jobs
- external services
- retry mechanisms
- messaging/events
- configuration

# Risks

Identify possible:

- regression risks
- edge cases
- transaction issues
- consistency issues
- retry issues

# Unknowns

List anything that could not be determined confidently.

Do not guess.

# Implementation Guidance

Give the Developer Agent a recommended implementation order.

The analysis must be based on actual Graphify and source-code
findings, not assumptions."""

# At the end, add an AI-REPORT section that summarizes the AI
# resources consumed during the analysis, including number
# of project artifacts inspected, number of MCP tool calls, and
# any other relevant usage metrics available.
# """

        return self.codex.run(prompt)


if __name__ == "__main__":

    story = """
Haw many modules are in this project?
"""

    analyzer = AnalyzerAgent()

    analysis = analyzer.analyze(story)

    print()
    print("=" * 80)
    print("ANALYZER RESULT")
    print("=" * 80)
    print()

    print(analysis)