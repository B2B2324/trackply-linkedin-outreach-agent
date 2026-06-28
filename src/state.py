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
    # network context — populated by scout
    relationship_type: str   # '1st' | '2nd' | '3rd' | 'open_link' | 'unknown'
    is_open_link: bool       # true → free DM without a connection request
    personalized_draft: str
    outreach_decision: Dict[str, Any]
    reply_example: str

class ConversationThread(TypedDict, total=False):
    lead_id: str
    messages: List[Dict[str, str]]
    status: str

class PendingReply(TypedDict, total=False):
    profile_url: str
    name: str
    reply_text: str
    thread_id: str
    conversation_url: str

class OutreachState(TypedDict, total=False):
    campaign_id: str
    run_date: str
    targets: List[LinkedInProfile]
    current_index: int
    messages_sent_today: int
    connection_requests_this_week: int   # tracked against weekly_connection_limit
    replies_received: int
    conversations: Dict[str, ConversationThread]
    errors: List[str]
    status: str
    last_action_at: Optional[str]
    supabase_lead_ids: Dict[str, str]
    human_approval_required: bool
    # Inbox polling — populated by inbox_poll_node, consumed by conversational_node
    pending_replies: List[PendingReply]