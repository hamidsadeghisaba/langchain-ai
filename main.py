from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain.agents import create_agent


llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key="sk-de578784f6cb4fb0b879f507ce87fab8",
    base_url="https://api.deepseek.com/v1",
)


@tool
def get_project_info() -> str:
    """Return information about the sample project."""
    return "Project name: langchain-poc, language: Python"


agent = create_agent(
    model=llm,
    tools=[get_project_info],
    system_prompt="You are a helpful software development assistant.",
)


result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "What is the project name and programming language?",
            }
        ]
    }
)


for message in result["messages"]:
    print(message)