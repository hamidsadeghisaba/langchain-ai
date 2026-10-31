from task_service import TaskWorkflowRuntime


def main() -> None:
    story = """
create a simple DTO class in Charisma-datamodel
"""

    with TaskWorkflowRuntime.create() as runtime:
        task = runtime.service.create_task(
            title="Sample Codex workflow",
            description=story,
            priority=10,
        )
        result = runtime.service.run_task(task.task_id)

        print("\n")
        print("=" * 70)
        print("ANALYZER RESULT")
        print("=" * 70)
        print(result.get("analysis", ""))
        print("=" * 70)

        decision = input("Approve analysis? [y/n]: ").strip().lower()
        if decision not in ("y", "yes"):
            runtime.service.reject_task(task.task_id)
            print("\nAnalysis rejected.")
            return

        result = runtime.service.approve_task(task.task_id)

        print("\n")
        print("=" * 70)
        print("DEVELOPMENT RESULT")
        print("=" * 70)
        print(result.get("development_result", ""))

        print("\n")
        print("=" * 70)
        print("TEST RESULT")
        print("=" * 70)
        print(result.get("test_result", ""))

        print("\n")
        print("=" * 70)
        print("WORKFLOW FINISHED")
        print("=" * 70)


if __name__ == "__main__":
    main()
