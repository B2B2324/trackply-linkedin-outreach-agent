import os
from dotenv import load_dotenv

load_dotenv()

# Langfuse integration for token usage & cost tracking
try:
    from langfuse.callback import CallbackHandler
    langfuse_handler = CallbackHandler(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")  # or self-hosted
    )
except ImportError:
    langfuse_handler = None
    print("[LLM] Langfuse not installed or keys missing - running without observability")

# Choose your LLM provider here (cheapest first for bulk work)
# Options: "openai", "anthropic" (Claude), "xai" (Grok), or use LiteLLM for easy switching
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # Change to "xai" or "openai" as needed

if LLM_PROVIDER == "anthropic":
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",  # or claude-3-haiku for cheaper bulk work
        temperature=0.7,
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
elif LLM_PROVIDER == "xai":
    # Grok via xAI - add when official LangChain integration is available or use OpenAI compatible
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="grok-2",  # or whatever current Grok model
        temperature=0.7,
        api_key=os.getenv("XAI_API_KEY"),
        base_url="https://api.x.ai/v1"  # xAI OpenAI-compatible endpoint if available
    )
else:
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY")
    )

def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM with optional Langfuse tracing."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    if langfuse_handler:
        # Langfuse will automatically trace when using LangChain callbacks
        response = llm.invoke(messages, config={"callbacks": [langfuse_handler]})
    else:
        response = llm.invoke(messages)
    
    return response.content.strip() if hasattr(response, 'content') else str(response)