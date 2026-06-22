from langgraph.graph import StateGraph, END
from src.state import OutreachState
# TODO: Import real node implementations when ready

# Placeholder implementations (expand these)
def supervisor_node(state: OutreachState) -> OutreachState:
    print("[Supervisor] Checking campaign status...")
    if state.get("messages_sent_today", 0) >= 25:
        print("[Supervisor] Daily limit reached. Pausing.")
        state["status"] = "paused"
        return state
    # Add more logic: check time since last action, reply rates, etc.
    return state

def scout_node(state: OutreachState) -> OutreachState:
    print("[Scout] Searching for high-intent profiles...")
    # TODO: Integrate Apify LinkedIn Profile Search or browser tool here
    # Example: state["targets"] = apify_client.run_actor(...)
    # For now, placeholder
    if not state.get("targets"):
        state["targets"] = [{
            "name": "Example User",
            "profile_url": "https://linkedin.com/in/example",
            "headline": "Open to Work | AI Evaluator | Prompt Engineer",
            "location": "United States",
            "about_snippet": "Actively looking for AI freelance and full-time opportunities.",
            "fit_score": 8.5,
            "why_qualified": "Strong match for AI gig tracking + targeted job search.",
            "recent_activity_keywords": ["AI", "job search", "freelance"]
        }]
    return state

def personalizer_node(state: OutreachState) -> OutreachState:
    print("[Personalizer] Generating personalized messages...")
    # TODO: Call LLM with personalizer_prompt + profile context
    for target in state.get("targets", []):
        target["draft_message"] = f"Hi {target['name'].split()[0]}, saw you're open to work... Trackply helped me with the same chaos."
    return state

def outreach_node(state: OutreachState) -> OutreachState:
    print("[Outreach] Logging outreach (review mode - not sending yet)...")
    # TODO: Integrate Supabase logging + optional real send
    for target in state.get("targets", []):
        # log_outreach(...)
        state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1
    return state

def conversational_node(state: OutreachState) -> OutreachState:
    print("[Conversational] Checking for replies...")
    # TODO: Poll for new messages or integrate with LinkedIn API/browser
    # Use conversational_prompt for replies
    return state

def build_graph():
    workflow = StateGraph(OutreachState)
    
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("personalizer", personalizer_node)
    workflow.add_node("outreach", outreach_node)
    workflow.add_node("conversational", conversational_node)
    
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "scout")
    workflow.add_edge("scout", "personalizer")
    workflow.add_edge("personalizer", "outreach")
    workflow.add_edge("outreach", "conversational")
    workflow.add_edge("conversational", "supervisor")
    
    # Add conditional edges later for human review, error handling, etc.
    
    return workflow.compile()

if __name__ == "__main__":
    app = build_graph()
    initial_state: OutreachState = {
        "campaign_id": "test-2026-06-22",
        "run_date": "2026-06-22",
        "targets": [],
        "current_index": 0,
        "messages_sent_today": 0,
        "replies_received": 0,
        "conversations": {},
        "errors": [],
        "status": "running",
        "last_action_at": None,
        "supabase_lead_ids": {}
    }
    result = app.invoke(initial_state)
    print(result)