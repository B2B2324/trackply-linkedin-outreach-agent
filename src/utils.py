import time
import random

def human_like_delay(min_seconds: int = 30, max_seconds: int = 120):
    """Add random delay to mimic human behavior."""
    delay = random.randint(min_seconds, max_seconds)
    print(f"[Utils] Human-like delay: {delay} seconds")
    time.sleep(delay)

def calculate_fit_score(profile: dict) -> float:
    """Simple heuristic or LLM-based scoring. Expand later."""
    score = 5.0
    headline = profile.get("headline", "").lower()
    if "open to work" in headline or "#opento work" in headline:
        score += 2.5
    if any(kw in headline for kw in ["ai", "prompt", "evaluator", "rlhf", "freelance"]):
        score += 1.5
    return min(score, 10.0)