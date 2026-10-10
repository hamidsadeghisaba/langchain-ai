from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from analyzerAgent import AnalyzerAgent
from developerAgent import DeveloperAgent


class AgentState(TypedDict):
    story: str
    analysis: str
    development_result: str


analyzer = AnalyzerAgent()
developer = DeveloperAgent()


def analyze_node(state: AgentState):
    analysis = analyzer.analyze(
        state["story"]
    )

    return {
        "analysis": analysis
    }


def human_review_node(state: AgentState):
    decision = interrupt({
        "type": "human_review",
        "message": "Review the analyzer result and approve it.",
    })

    if decision == "approve":
        return {}

    if decision == "reject":
        raise ValueError("Analysis rejected by human.")

    raise ValueError(
        f"Unknown human decision: {decision}"
    )


def develop_node(state: AgentState):
    development_result = developer.develop(
        analysis=state["analysis"],
    )

    return {
        "development_result": development_result
    }


def build_graph():

    checkpointer = MemorySaver()

    graph = StateGraph(AgentState)

    graph.add_node(
        "analyzer",
        analyze_node,
    )

    graph.add_node(
        "human_review",
        human_review_node,
    )

    graph.add_node(
        "developer",
        develop_node,
    )

    graph.add_edge(
        START,
        "analyzer",
    )

    graph.add_edge(
        "analyzer",
        "human_review",
    )

    graph.add_edge(
        "human_review",
        "developer",
    )

    graph.add_edge(
        "developer",
        END,
    )

    return graph.compile(
        checkpointer=checkpointer
    )
