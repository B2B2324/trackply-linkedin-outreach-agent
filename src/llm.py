from langchain.chat_models import ChatOpenAI  # or ChatAnthropic / Grok equivalent
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
import os

load_dotenv()

# Configure your preferred LLM here (Grok, Claude, OpenAI, etc.)
llm = ChatOpenAI(
    model="gpt-4o-mini",  # or your preferred model
    temperature=0.7,
    api_key=os.getenv("OPENAI_API_KEY")
)

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Simple helper to call LLM with system + user prompt."""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]
    response = llm.invoke(messages)
    return response.content.strip()