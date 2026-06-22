from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime

class LinkedInProfile(TypedDict, total=False):
    name: str
    profile_url: str
    headline: str
    location: str
    about_snippet: str
    fit_score: float
    why_qualified: str
    recent_activity_keywords: List[str]
    personalized_draft: str
    outreach_decision: Dict[str, Any]
    reply_example: str  # for testing

class ConversationThread(TypedDict, total=False):
    lead_id: str
    messages: List[Dict[str, str]]
    status: str

class OutreachState(TypedDict, total=False):
    campaign_id: str
    run_date: str
    targets: List[LinkedInProfile]
    current_index: int
    messages_sent_today: int
    replies_received: int
    conversations: Dict[str, ConversationThread]
    errors: List[str]
    status: str
    last_action_at: Optional[str]
    supabase_lead_ids: Dict[str, str]
    human_approval_required: bool