from src.supabase_client import supabase

# Trackply subscription tiers
TIERS = {
    "free": {"linkedin_outreach": 5, "seo_articles": 2, "personal_brain_recall": 20, "reminders": 5},
    "pro": {"linkedin_outreach": 50, "seo_articles": 20, "personal_brain_recall": 200, "reminders": 50},
    "pro_max": {"linkedin_outreach": 200, "seo_articles": 100, "personal_brain_recall": 1000, "reminders": 200},
    "ultra": {"linkedin_outreach": -1, "seo_articles": -1, "personal_brain_recall": -1, "reminders": -1}  # unlimited
}

def get_user_tier(user_id: str) -> str:
    """Fetch user's current Trackply subscription tier."""
    # TODO: Query actual Trackply users/subscriptions table
    response = supabase.table("users").select("subscription_tier").eq("id", user_id).execute()
    return response.data[0]["subscription_tier"] if response.data else "free"

def check_tier_access(user_id: str, feature: str) -> bool:
    tier = get_user_tier(user_id)
    limits = TIERS.get(tier, TIERS["free"])
    
    if limits.get(feature, 0) == -1:
        return True  # unlimited
    
    # TODO: Check actual usage count this month
    current_usage = 0  # placeholder
    return current_usage < limits.get(feature, 0)

def get_remaining_quota(user_id: str, feature: str) -> int:
    tier = get_user_tier(user_id)
    limits = TIERS.get(tier, TIERS["free"])
    if limits.get(feature, 0) == -1:
        return -1
    # TODO: Calculate remaining
    return limits.get(feature, 0)