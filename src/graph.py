from langgraph.graph import StateGraph, END
from src.state import OutreachState
# Import agent nodes (to be implemented)

# Placeholder nodes - replace with real implementations
def scout_node(state: OutreachState):
    # TODO: Call Apify or browser tool to find profiles
    # Update state['targets']
    print("Scout node running...")
    return state

def personalizer_node(state: OutreachState):
    # TODO: For each target, generate personalized message using prompt
    print("Personalizer node running...")
    return state

def outreach_node(state: OutreachState):
    # TODO: Log to Supabase, optionally send (review mode first)
    # Enforce rate limits
    print("Outreach node running...")
    return state

def supervisor_node(state: OutreachState):
    # Check daily caps, decide next step or END
    if state['messages_sent_today'] > 25:
        state['status'] = 'paused'
        return END
    return state

def build_graph():
    workflow = StateGraph(OutreachState)
    workflow.add_node("scout", scout_node)
    workflow.add_node("personalizer", personalizer_node)
    workflow.add_node("outreach", outreach_node)
    workflow.add_node("supervisor", supervisor_node)
    
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "scout")
    workflow.add_edge("scout", "personalizer")
    workflow.add_edge("personalizer", "outreach")
    workflow.add_edge("outreach", "supervisor")
    
    return workflow.compile()

if __name__ == "__main__":
    app = build_graph()
    initial_state = {
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