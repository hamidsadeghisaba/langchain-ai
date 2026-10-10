from openai_codex import (
    Codex,
    CodexConfig,
    ApprovalMode,
    Sandbox,
)

REPO = r"E:\project\dotin\PTS\settle"

GRAPHIFY_PYTHON = (
    r"C:\Users\h.sadeghii\AppData\Local\Programs"
    r"\Python\Python314\python.exe"
)

GRAPH = r"E:\project\dotin\PTS\graphify-out\graph.json"


def main():
    config = CodexConfig(
        cwd=REPO,
        config_overrides=(
            f'mcp_servers.graphify-production.command="{GRAPHIFY_PYTHON}"',
            f"mcp_servers.graphify-production.args=['-m', 'graphify.serve', '{GRAPH}']",
        ),
    )

    with Codex(config) as codex:
        thread = codex.thread_start(
            cwd=REPO,
            approval_mode=ApprovalMode.deny_all,
            sandbox=Sandbox.full_access,
        )

        result = thread.run("""
You are testing Graphify MCP.

MANDATORY:
1. Call the Graphify MCP tool `graph_stats`.
2. Do this BEFORE reading any source code.
3. Do NOT use shell.
4. Do NOT use filesystem tools.
5. Do NOT guess.

If Graphify cannot be called, return exactly:

GRAPHIFY_NOT_AVAILABLE

Otherwise return:

GRAPHIFY_AVAILABLE

Then provide:
- MCP server name
- MCP tool name
- actual graph_stats result
""")

        print("========== CODEX RESULT ==========")
        print(result.final_response)
        print("===================================")


if __name__ == "__main__":
    main()