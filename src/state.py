from typing import TypedDict, List, Dict, Optional
from datetime import datetime

class LinkedInProfile(TypedDict):
    name: str
    profile_url: str
    headline: str
    location: str
    about_snippet: str
    fit_score: float
    why_qualified: str
    recent_activity_keywords: List[str]

class ConversationThread(TypedDict):
    lead_id: str
    messages: List[Dict]
    status: str  # pending, replied, qualified, converted, etc.

class OutreachState(TypedDict):
    campaign_id: str
    run_date: str
    targets: List[LinkedInProfile]
    current_index: int
    messages_sent_today: int
    replies_received: int
    conversations: Dict[str, ConversationThread]
    errors: List[str]
    status: str  # running, paused, needs_review, completed
    last_action_at: Optional[str]
    supabase_lead_ids: Dict[str, str]  # profile_url -> lead_id