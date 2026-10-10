from dataclasses import dataclass, field
import os
import time

from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

from config import CODEX_CMD


@dataclass(frozen=True)
class GraphifyServerConfig:
    name: str
    graph_path: str
    python: str


@dataclass(frozen=True)
class CodexAgentConfig:
    repo: str

    codex_bin: str = CODEX_CMD

    model: str = "deepseek-v4-flash"
    model_provider: str = "avalai"

    graphify_servers: tuple[GraphifyServerConfig, ...] = field(
        default_factory=tuple
    )


@dataclass
class AgentResult:
    response: str

    # AI telemetry
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0

    # MCP / artifacts telemetry
    mcp_calls: int = 0
    mcp_tools: dict[str, int] = field(default_factory=dict)
    project_artifacts: int = 0
    inspected_artifacts: list[str] = field(default_factory=list)


class MyCodexAgent:

    def __init__(self, config: CodexAgentConfig):
        self.config = config
        self._validate()

        self.codex_config = CodexConfig(
            codex_bin=config.codex_bin,
            config_overrides=self._build_config_overrides(),
            cwd=config.repo,
        )

    def _validate(self):
        if not os.path.isdir(self.config.repo):
            raise ValueError(
                f"Repository does not exist: {self.config.repo}"
            )

        if not os.path.isfile(self.config.codex_bin):
            raise ValueError(
                f"Codex executable does not exist: {self.config.codex_bin}"
            )

        if not self.config.model:
            raise ValueError("model must not be empty")

        if not self.config.model_provider:
            raise ValueError("model_provider must not be empty")

        for server in self.config.graphify_servers:
            if not server.name:
                raise ValueError(
                    "Graphify server name must not be empty"
                )

            if not os.path.isfile(server.graph_path):
                raise ValueError(
                    f"Graphify graph does not exist: "
                    f"{server.graph_path}"
                )

            if not os.path.isfile(server.python):
                raise ValueError(
                    f"Graphify Python executable does not exist: "
                    f"{server.python}"
                )

    def _build_config_overrides(self) -> tuple[str, ...]:
        overrides = [
            f'model="{self.config.model}"',
            f'model_provider="{self.config.model_provider}"',
        ]

        for server in self.config.graphify_servers:
            overrides.append(
                f'mcp_servers.{server.name}.command="{server.python}"'
            )

            overrides.append(
                f"mcp_servers.{server.name}.args="
                f"['-m', 'graphify.serve', '{server.graph_path}']"
            )

        return tuple(overrides)

    def run(self, prompt: str) -> AgentResult:
        started = time.perf_counter()

        with Codex(self.codex_config) as codex:
            thread = codex.thread_start(
                cwd=self.config.repo,
                approval_mode=ApprovalMode.deny_all,
                sandbox=Sandbox.full_access,
            )

            result = thread.run(prompt)

        duration_ms = int(
            (time.perf_counter() - started) * 1000
        )

        # -----------------------------
        # Usage / telemetry
        # -----------------------------

        usage = getattr(result, "usage", None)
        last_usage = getattr(usage, "last", None)

        input_tokens = getattr(
            last_usage, "input_tokens", 0
        ) if last_usage else 0

        cached_input_tokens = getattr(
            last_usage, "cached_input_tokens", 0
        ) if last_usage else 0

        output_tokens = getattr(
            last_usage, "output_tokens", 0
        ) if last_usage else 0

        reasoning_output_tokens = getattr(
            last_usage, "reasoning_output_tokens", 0
        ) if last_usage else 0

        total_tokens = getattr(
            last_usage, "total_tokens", 0
        ) if last_usage else 0

        # -----------------------------
        # Print telemetry
        # -----------------------------

        print()
        print("=" * 70)
        print("CODEX AGENT REPORT")
        print("=" * 70)

        print(f"MODEL: {self.config.model}")
        print(f"PROVIDER: {self.config.model_provider}")
        print(f"INPUT TOKENS: {input_tokens}")
        print(f"CACHED INPUT TOKENS: {cached_input_tokens}")
        print(f"OUTPUT TOKENS: {output_tokens}")
        print(f"REASONING TOKENS: {reasoning_output_tokens}")
        print(f"TOTAL TOKENS: {total_tokens}")
        print(f"DURATION: {duration_ms} ms")

        print("=" * 70)
        print()

        # return AgentResult(
        #     response=result.final_response,
        #     input_tokens=input_tokens,
        #     cached_input_tokens=cached_input_tokens,
        #     output_tokens=output_tokens,
        #     reasoning_output_tokens=reasoning_output_tokens,
        #     total_tokens=total_tokens,
        #     duration_ms=duration_ms,
        #     mcp_calls=0,
        #     mcp_tools={},
        #     project_artifacts=0,
        #     inspected_artifacts=[],
        # )
        return result.final_response