from langgraph.types import Command

from workflow import build_graph


def main():

    story = """
create a simple DTO class in Charisma-datamodel
"""

    graph = build_graph()

    config = {
        "configurable": {
            "thread_id": "task-001"
        }
    }

    # ==================================================
    # START WORKFLOW
    # ==================================================

    result = graph.invoke(
        {
            "story": story,
            "analysis": "",
            "development_result": "",
        },
        config,
    )

    # ==================================================
    # HUMAN REVIEW
    # ==================================================

    interrupts = result.get("__interrupt__")

    if interrupts:

        print("\n")
        print("=" * 70)
        print("ANALYZER RESULT")
        print("=" * 70)

        print(result.get("analysis", ""))

        print("\n")
        print("=" * 70)

        decision = input(
            "Approve analysis? [y/n]: "
        ).strip().lower()

        if decision not in ("y", "yes"):

            print("\nAnalysis rejected.")
            return

        # ==================================================
        # RESUME WORKFLOW
        # ==================================================

        result = graph.invoke(
            Command(
                resume="approve"
            ),
            config,
        )

    # ==================================================
    # DEVELOPMENT RESULT
    # ==================================================

    print("\n")
    print("=" * 70)
    print("DEVELOPMENT RESULT")
    print("=" * 70)

    print(
        result.get(
            "development_result",
            ""
        )
    )

    print("\n")
    print("=" * 70)
    print("WORKFLOW FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    main()
