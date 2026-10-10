from pathlib import Path

from langchain_core.tools import tool

from config import PROJECT_PATH


@tool
def list_project_files() -> str:
    """
    List files in the project repository.
    Use this tool to understand the project structure.
    """

    files = []

    for path in PROJECT_PATH.rglob("*"):

        if path.is_file():

            relative_path = path.relative_to(PROJECT_PATH)

            files.append(str(relative_path))

    return "\n".join(sorted(files))


@tool
def read_project_file(file_path: str) -> str:
    """
    Read a text file from the project repository.
    """

    path = (PROJECT_PATH / file_path).resolve()

    if PROJECT_PATH not in path.parents:
        return "Access denied."

    if not path.is_file():
        return f"File not found: {file_path}"

    try:

        return path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return (
            f"Cannot read {file_path} as a UTF-8 text file."
        )