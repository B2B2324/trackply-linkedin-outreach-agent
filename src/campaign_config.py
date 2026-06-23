from typing import TypedDict

class CampaignConfig(TypedDict, total=False):
    daily_limit: int
    min_delay_seconds: int
    max_delay_seconds: int
    require_human_approval: bool
    target_keywords: list[str]
    excluded_locations: list[str]
    llm_model: str
    review_mode: bool

default_config: CampaignConfig = {
    "daily_limit": 25,
    "min_delay_seconds": 30,
    "max_delay_seconds": 120,
    "require_human_approval": True,
    "target_keywords": ["open to work", "ai evaluator", "prompt engineer", "rlhf", "freelance ai", "job seeker"],
    "excluded_locations": [],
    "llm_model": "gpt-4o-mini",
    "review_mode": True
}

def load_campaign_config(campaign_id: str = None) -> CampaignConfig:
    """Load config (expand later with DB or file)."""
    return default_config