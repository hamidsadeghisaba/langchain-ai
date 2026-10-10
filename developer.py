from developer_tool import developer_agent
from state import WorkflowState


def developer(state: WorkflowState):

    task = f"""
Original Story:

{state["story"]}


Analyzer Result:

{state["analysis"]}


Implement the task according to the approved analysis.
"""

    report = developer_agent.invoke(
        {
            "task": task
        }
    )

    return {
        "developer_report": report
    }