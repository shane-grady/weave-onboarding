from composio import Composio
from composio_langchain import LangchainProvider
from langchain_anthropic import ChatAnthropic
import os
from dotenv import load_dotenv

load_dotenv(override=True)

composio = Composio(
    api_key=os.getenv("COMPOSIO_API_KEY"),
    provider=LangchainProvider(),
)

llm = ChatAnthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-haiku-4-5-20251001",
    max_tokens=4096,
)
