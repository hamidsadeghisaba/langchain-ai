from typing import TypedDict


class WorkflowState(TypedDict, total=False):

    story: str

    analysis: str

    human_decision: str

    developer_report: str