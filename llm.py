from langchain_openai import ChatOpenAI


llm = ChatOpenAI(
    model="deepseek-v4-flash",
    api_key="YOUR_DEEPSEEK_API_KEY",
    base_url="https://api.deepseek.com/v1",
)