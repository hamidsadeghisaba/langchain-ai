from openai_codex import Codex, Sandbox, CodexConfig
from pathlib import Path


def run_analyzer(prompt: str):
    
    agent_md = Path(r".\docs\md\settle\ANALYZER_AGENTS.md").read_text(encoding="utf-8")
    architect_md = Path(r".\docs\md\settle\ARCHITECTURE.md").read_text(encoding="utf-8")
    
    full_prompt = f"""
You are a Test Analyzer.

## AGENT.md

{agent_md}

## ARCHITECT.md

{architect_md}

## Task

{prompt}
"""
    config = CodexConfig(
        cwd=r"E:\project\dotin\PTS\settle",
        config_overrides=(
            'mcp_servers.graphify-production.command="python"',
            'mcp_servers.graphify-production.args=["-m","graphify.serve","E:/project/dotin/PTS/graphify-out/graph.json"]',
        ),
    )
    with Codex(config) as codex:
        codex.login_api_key("sk-de578784f6cb4fb0b879f507ce87fab8")
        
        thread = codex.thread_start(
            cwd=r"E:\project\dotin\PTS\settle",
            model="deepseek-v4-flash",
            model_provider="deepseek",
            sandbox=Sandbox.full_access
        )

        result = thread.run(prompt)

        return result.final_response


def main():
    result = run_analyzer(prompt = """
You are testing Graphify MCP connectivity.

MANDATORY:
1. Before reading any source file or using shell commands,
   call the Graphify MCP tool `graph_stats`.
2. Report the actual statistics returned by that tool.
3. If the tool is unavailable or fails, report the error.
   Do not guess or fabricate statistics.
4. Do not modify any files.

Return:
- Whether graph_stats was called successfully
- The actual graph statistics
- The name of the MCP tool used
""")
    print(result)


if __name__ == "__main__":
    main()