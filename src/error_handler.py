import time
import random

def retry_with_backoff(func, max_retries=3, base_delay=2):
    """Decorator-like retry with exponential backoff."""
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"[ErrorHandler] Retry {attempt+1}/{max_retries} after error: {e}. Waiting {delay:.1f}s")
                time.sleep(delay)
        return None
    return wrapper

def safe_execute(node_func, state, default_return=None):
    """Wrap node execution with error catching."""
    try:
        return node_func(state)
    except Exception as e:
        print(f"[ErrorHandler] Node failed: {e}")
        state.setdefault("errors", []).append(str(e))
        return default_return or state