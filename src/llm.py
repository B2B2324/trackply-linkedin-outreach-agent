from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()

try:
    from langfuse.callback import CallbackHandler as _LFHandler
    _langfuse_available = True
except ImportError:
    _langfuse_available = False


def _langfuse_handler():
    """Return a Langfuse callback handler if keys are set, else None."""
    if not _langfuse_available:
        return None
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        return None
    try:
        return _LFHandler(
            public_key=pk,
            secret_key=sk,
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
    except Exception:
        return None


def _build_llm():
    """Build the LLM client from current environment variables (called per-request)."""
    provider = os.getenv("LLM_PROVIDER", "anthropic")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set — add it to Streamlit secrets")
        return ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0.7,
            api_key=key,
        )
    elif provider == "xai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="grok-3",
            temperature=0.7,
            api_key=os.getenv("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=os.getenv("OPENAI_API_KEY"),
        )


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Call LLM with optional Langfuse tracing. Builds client fresh from current env."""
    llm     = _build_llm()
    handler = _langfuse_handler()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    if handler:
        response = llm.invoke(messages, config={"callbacks": [handler]})
    else:
        response = llm.invoke(messages)
    return response.content.strip() if hasattr(response, "content") else str(response)
