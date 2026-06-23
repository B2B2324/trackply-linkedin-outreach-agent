from src.supabase_client import supabase

# Knowledge Carry-over from LinkedIn Outreach to Trackply Private Brain

def create_initial_knowledge_base(lead_id: str, conversation_summary: str, signals: list):
    """
    When a lead signs up via tracked LinkedIn link, create initial context
    for their Trackply Private Brain / Kemba (Job Coach).
    """
    data = {
        "lead_id": lead_id,
        "initial_context": conversation_summary,
        "interest_signals": signals,  # e.g. ["gig_tracking", "meta_agent"]
        "source": "linkedin_outreach",
        "created_at": "now()"
    }
    response = supabase.table("user_knowledge_base").insert(data).execute()
    print(f"[Knowledge Carry-over] Created initial Private Brain context for lead {lead_id}")
    return response.data

# Example usage when lead signs up
def on_lead_signup(lead_id: str, conversation_thread: list):
    summary = "Lead showed interest in gig tracking and Meta Agent during LinkedIn conversation."
    signals = ["gig_tracking", "meta_agent"]
    return create_initial_knowledge_base(lead_id, summary, signals)