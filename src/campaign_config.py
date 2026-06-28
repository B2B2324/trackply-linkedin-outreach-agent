from typing import TypedDict

class CampaignConfig(TypedDict, total=False):
    daily_limit: int
    weekly_connection_limit: int   # LinkedIn caps ~100/week; stay well under
    max_conversational_replies: int  # replies sent per run (inbox poll cap)
    conversational_enabled: bool     # False = skip inbox polling entirely
    min_delay_seconds: int
    max_delay_seconds: int
    require_human_approval: bool
    target_keywords: list[str]
    excluded_locations: list[str]
    llm_model: str
    review_mode: bool

default_config: CampaignConfig = {
    # LinkedIn real-world limits:
    #   ~100-200 connection requests/week before account warning
    #   DMs to 1st-degree / OpenLink: no hard cap, but stay human-paced
    #   ~50/day total is aggressive-but-safe; a human researcher does 80-100
    "daily_limit": 50,
    "weekly_connection_limit": 80,      # stays under LinkedIn's ~100 soft cap
    "max_conversational_replies": 10,
    "conversational_enabled": False,    # enable once outreach is confirmed working
    "min_delay_seconds": 8,
    "max_delay_seconds": 25,
    "require_human_approval": True,
    "target_keywords": ["open to work", "ai evaluator", "prompt engineer", "rlhf", "freelance ai", "job seeker"],
    "excluded_locations": [],
    "llm_model": "claude-sonnet-4-6",
    "review_mode": True,               # True = draft only — toggle via dashboard "Run Live" button
}

def load_campaign_config(campaign_id: str = None) -> CampaignConfig:
    """Load config (expand later with DB or file)."""
    return default_config