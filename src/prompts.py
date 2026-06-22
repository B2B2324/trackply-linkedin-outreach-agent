import os

def load_prompt(filename: str) -> str:
    """Load prompt from prompts/ directory."""
    base_path = os.path.join(os.path.dirname(__file__), "..", "prompts")
    path = os.path.join(base_path, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()