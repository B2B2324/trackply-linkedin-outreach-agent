from typing import TypedDict

class CampaignConfig(TypedDict, total=False):
    daily_limit: int
    weekly_connection_limit: int   # LinkedIn caps ~100/week; stay well under
    min_delay_seconds: int
    max_delay_seconds: int
    require_human_approval: bool
    target_keywords: list[str]
    excluded_locations: list[str]
    llm_model: str
    review_mode: bool

default_config: CampaignConfig = {
    "daily_limit": 80,
    "weekly_connection_limit": 80,   # LinkedIn hard cap ~100/week; stay under
    "min_delay_seconds": 8,
    "max_delay_seconds": 25,
    "require_human_approval": True,
    "target_keywords": ["open to work", "ai evaluator", "prompt engineer", "rlhf", "freelance ai", "job seeker"],
    "excluded_locations": [],
    "llm_model": "claude-3-5-sonnet-20241022",
    "review_mode": True,
}

def load_campaign_config(campaign_id: str = None) -> CampaignConfig:
    """Load config (expand later with DB or file)."""
    return default_config