def decide_daily_actions(performance_data: dict):
    """Smarter supervisor that decides what to run based on performance/cost."""
    actions = ["linkedin_outreach"]
    
    if performance_data.get("reply_rate", 0) > 15:
        actions.append("seo_content")  # Double down on content if converting well
    
    if performance_data.get("token_spend_24h", 0) < 5:
        actions.append("reddit_engagement")  # More Reddit if cheap
    
    return actions

# Example
if __name__ == "__main__":
    print(decide_daily_actions({"reply_rate": 18, "token_spend_24h": 4.2}))