from openai_codex import Codex, Sandbox

with Codex() as codex:
    thread = codex.thread_start(
        sandbox=Sandbox.read_only
    )

    result = thread.run(
        "Inspect this project and tell me what files it contains."
    )

    print(result.final_response)

    