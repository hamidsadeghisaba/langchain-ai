from config import GRAPHIPY_JSON, GRAPHIPY_PRODUCT, GRAPHIPY_TEST, PUBLIC_MODEL, PUBLIC_PROVIDER, PYTHON_CMD, TEST_PROJECT_PATH, PROJECT_PATH
from myCodexAgent import (
    MyCodexAgent,
    CodexAgentConfig,
    GraphifyServerConfig,
)

class TesterAgent:

    def __init__(self):
        self.test_repo = str(TEST_PROJECT_PATH)

        self.production_repo = str(PROJECT_PATH)

        self.codex = MyCodexAgent(
            CodexAgentConfig(
                repo=self.test_repo,

                model=PUBLIC_MODEL,
                model_provider=PUBLIC_PROVIDER,

                graphify_servers=(
                    GraphifyServerConfig(
                        name=GRAPHIPY_PRODUCT,
                        graph_path=( PROJECT_PATH / GRAPHIPY_JSON ),
                        python=PYTHON_CMD,
                    ),
                    GraphifyServerConfig(
                        name=GRAPHIPY_TEST,
                        graph_path=( TEST_PROJECT_PATH / GRAPHIPY_JSON ),
                        python=PYTHON_CMD,
                    ),
                ),
            )
        )

    def test(
        self,
        story: str,
        development_result: str,
        test_analysis: str,
    ) -> str:

        if not story or not story.strip():
            raise ValueError("Story must not be empty")

        if not development_result or not development_result.strip():
            raise ValueError(
                "Development result must not be empty"
            )

        if not test_analysis or not test_analysis.strip():
            raise ValueError(
                "Test analysis must not be empty"
            )

        prompt = f"""
You are the Tester Agent in a multi-agent software development
workflow.

Your responsibility is to implement and execute integration tests
for the requested production change.

You are NOT the Developer Agent.
You must not implement production features or change production
source code.

==================================================
STORY
==================================================

{story}

==================================================
DEVELOPMENT RESULT
==================================================

{development_result}

==================================================
TEST ANALYSIS
==================================================

{test_analysis}

==================================================
REPOSITORIES
==================================================

Integration-test repository (your working repository):

{self.test_repo}

Production repository (read-only reference):

{self.production_repo}

==================================================
GRAPHIFY SERVERS
==================================================

graphify-production:
Use it to understand production jobs, services, classes, tables,
dependencies, and execution flow.

graphify-test:
Use it to understand the integration-test structure, existing
test classes, test utilities, fixtures, and test execution patterns.

Do not confuse the two graphs.

==================================================
MANDATORY WORKFLOW
==================================================

1. Start with Graphify investigation.

2. Use graphify-production to independently verify the production
   behavior described in the story and test analysis.

3. Use graphify-test to identify the most relevant existing
   integration tests and reuse their patterns.

4. Inspect the actual source and test files after Graphify.

5. Treat production source code as the source of truth.

6. Treat the Test Analysis as guidance, not unquestionable truth.
   If it conflicts with source code or existing test conventions,
   investigate and report the discrepancy.

7. Make changes only in the integration-test repository.

8. Implement only tests required by the story.

9. Run the most relevant tests using the repository's existing
   build system and conventions.

10. Report actual command results. Never claim a test passed unless
    it was executed and passed.

==================================================
IMPLEMENTATION RULES
==================================================

- Reuse existing integration-test patterns and utilities.
- Do not invent database table names, columns, job names, or business
  rules when they cannot be established from source or schema.
- Do not add unnecessary dependencies.
- Do not refactor unrelated tests.
- Do not modify production source code.
- Do not change build configuration unless required for the test;
  explain the reason if a change is necessary.
- Do not create commits or push changes.
- Do not change branches, reset the repository, or discard user work.
- If required information is missing, do not guess. Explain what is
  missing and why it prevents reliable test implementation.
- Do not claim that an unexecuted test passed.

==================================================
FINAL RESPONSE
==================================================

Return these sections:

# Test Implementation Summary

# Changed Test Components

# Test Execution

For each executed command, report:
- command
- whether it ran successfully
- actual test result

# Failures

Describe failures and distinguish test failures from build or
environment failures.

# Remaining Issues

List unresolved requirements, missing inputs, or tests that could
not be executed.

Do not include token usage, MCP statistics, or an AI report.
"""

        result = self.codex.run(prompt)
        return result.response