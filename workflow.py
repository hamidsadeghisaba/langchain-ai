from __future__ import annotations

from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from service.repository.task_repository import PersistentTaskRepository

from service.model.task_queue import (
    InvalidTaskTransitionError,
    Task,
    TaskStage,
)


class AgentState(TypedDict, total=False):
    task_id: str
    title: str
    story: str
    stage: str
    analysis: str
    development_result: str
    test_result: str


class AnalyzerAgentProtocol(Protocol):
    def analyze(self, story: str) -> str: ...


class DeveloperAgentProtocol(Protocol):
    def develop(self, analysis: str) -> str: ...


class TesterAgentProtocol(Protocol):
    def test(
        self,
        story: str,
        development_result: str,
        test_analysis: str | None = None,
    ) -> str: ...


def _error_text(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


class WorkflowNodes:
    """LangGraph nodes backed by the durable stage queues."""

    def __init__(
        self,
        repository: PersistentTaskRepository,
        analyzer: AnalyzerAgentProtocol,
        developer: DeveloperAgentProtocol,
        tester: TesterAgentProtocol,
        *,
        worker_id: str = "langgraph",
    ):
        self.repository = repository
        self.analyzer = analyzer
        self.developer = developer
        self.tester = tester
        self.worker_id = worker_id

    def _claim(self, state: AgentState, stage: TaskStage):
        task_id = state.get("task_id", "")
        if not task_id:
            raise ValueError("Workflow state is missing task_id.")

        claim = self.repository.claim_task(
            task_id,
            expected_stage=stage,
            worker_id=self.worker_id,
        )
        if claim is None:
            current = self.repository.get_task(task_id)
            if current.stage is TaskStage.DEVELOPER and current.approved_at is None:
                raise InvalidTaskTransitionError(
                    "The Developer stage is waiting for human approval."
                )
            raise InvalidTaskTransitionError(
                f"Task {task_id} is not claimable for {stage.value}; "
                f"current stage/status is {current.stage.value}/{current.status.value}."
            )
        return claim

    def analyzer_node(self, state: AgentState) -> AgentState:
        claim = self._claim(state, TaskStage.ANALYZER)
        try:
            analysis = self.analyzer.analyze(state["story"])
        except Exception as error:
            self.repository.record_error(
                state["task_id"],
                _error_text(error),
                execution_token=claim.execution_token,
            )
            raise

        self.repository.move_to_next_stage(
            state["task_id"],
            analysis,
            execution_token=claim.execution_token,
        )
        return {
            "analysis": analysis,
            "stage": TaskStage.DEVELOPER.value,
        }

    def human_review_node(self, state: AgentState) -> AgentState:
        decision = interrupt(
            {
                "type": "human_review",
                "message": "Review the analyzer result and approve it.",
                "task_id": state["task_id"],
                "title": state.get("title", ""),
                "analysis": state.get("analysis", ""),
            }
        )

        if decision == "approve":
            self.repository.approve_task(state["task_id"])
            return {}

        if decision == "reject":
            message = "Analysis rejected by human."
            self.repository.fail_awaiting_review(state["task_id"], message)
            raise ValueError(message)

        message = f"Unknown human decision: {decision}"
        self.repository.fail_awaiting_review(state["task_id"], message)
        raise ValueError(message)

    def developer_node(self, state: AgentState) -> AgentState:
        claim = self._claim(state, TaskStage.DEVELOPER)
        try:
            development_result = self.developer.develop(state["analysis"])
        except Exception as error:
            self.repository.record_error(
                state["task_id"],
                _error_text(error),
                execution_token=claim.execution_token,
            )
            raise

        self.repository.move_to_next_stage(
            state["task_id"],
            development_result,
            execution_token=claim.execution_token,
        )
        return {
            "development_result": development_result,
            "stage": TaskStage.TESTER.value,
        }

    def tester_node(self, state: AgentState) -> AgentState:
        claim = self._claim(state, TaskStage.TESTER)
        try:
            test_result = self.tester.test(
                story=state["story"],
                development_result=state["development_result"],
                test_analysis=None,
            )
        except Exception as error:
            self.repository.record_error(
                state["task_id"],
                _error_text(error),
                execution_token=claim.execution_token,
            )
            raise

        self.repository.move_to_next_stage(
            state["task_id"],
            test_result,
            execution_token=claim.execution_token,
        )
        return {
            "test_result": test_result,
            "stage": TaskStage.TESTER.value,
        }


def _select_start_node(state: AgentState) -> str:
    try:
        stage = TaskStage(state["stage"])
    except (KeyError, ValueError) as error:
        raise ValueError(
            f"Workflow state has an invalid or missing stage: {state.get('stage')}"
        ) from error

    return {
        TaskStage.ANALYZER: "analyzer",
        TaskStage.DEVELOPER: "developer",
        TaskStage.TESTER: "tester",
    }[stage]


def build_graph(
    *,
    repository: PersistentTaskRepository,
    analyzer: AnalyzerAgentProtocol,
    developer: DeveloperAgentProtocol,
    tester: TesterAgentProtocol,
    checkpointer,
):
    """Build the existing workflow with durable state and queue transitions."""

    if checkpointer is None:
        raise ValueError("A checkpointer is required.")

    nodes = WorkflowNodes(
        repository=repository,
        analyzer=analyzer,
        developer=developer,
        tester=tester,
    )

    graph = StateGraph(AgentState)
    graph.add_node("analyzer", nodes.analyzer_node)
    graph.add_node("human_review", nodes.human_review_node)
    graph.add_node("developer", nodes.developer_node)
    graph.add_node("tester", nodes.tester_node)

    graph.add_conditional_edges(
        START,
        _select_start_node,
        {
            "analyzer": "analyzer",
            "developer": "developer",
            "tester": "tester",
        },
    )
    graph.add_edge("analyzer", "human_review")
    graph.add_edge("human_review", "developer")
    graph.add_edge("developer", "tester")
    graph.add_edge("tester", END)

    return graph.compile(checkpointer=checkpointer)


def initial_state(task: Task) -> AgentState:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "story": task.description,
        "stage": task.stage.value,
        "analysis": task.analysis_result,
        "development_result": task.development_result,
        "test_result": task.test_result,
    }
