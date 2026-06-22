from src.state import OutreachState
from src.llm import call_llm
from src.supabase_client import log_lead, log_outreach, save_conversation
from src.prompts import load_prompt  # helper to load prompt files

import json

def supervisor_node(state: OutreachState) -> OutreachState:
    print("[Supervisor] Evaluating campaign...")
    if state.get("messages_sent_today", 0) >= 25:
        state["status"] = "paused"
        print("[Supervisor] Daily cap reached.")
    # Add reply rate monitoring, time-based pauses, etc. later
    return state

def scout_node(state: OutreachState) -> OutreachState:
    print("[Scout] Discovering profiles...")
    # TODO: Replace with real Apify call or browser scraping
    # For demo, we keep the example from previous
    if not state.get("targets"):
        state["targets"] = [{
            "name": "Alex Rivera",
            "profile_url": "https://www.linkedin.com/in/alex-rivera-ai",
            "headline": "Open to Work | AI Prompt Engineer & RLHF Evaluator",
            "location": "United States (Remote)",
            "about_snippet": "Helping companies with AI evaluation and prompt engineering. Actively exploring full-time and contract opportunities.",
            "fit_score": 9.2,
            "why_qualified": "Perfect match for AI gig tracking + targeted job search tools.",
            "recent_activity_keywords": ["AI", "prompt engineering", "job search", "freelance"]
        }]
    for t in state["targets"]:
        lead = log_lead(t)
        if lead:
            state.setdefault("supabase_lead_ids", {})[t["profile_url"]] = lead["id"]
    return state

def personalizer_node(state: OutreachState) -> OutreachState:
    print("[Personalizer] Crafting personalized messages with LLM...")
    system_prompt = load_prompt("personalizer_prompt.txt")
    for target in state.get("targets", []):
        user_prompt = f"Profile: {json.dumps(target, indent=2)}\n\nGenerate 2-3 natural message variations for Trackply outreach."
        try:
            draft = call_llm(system_prompt, user_prompt)
            target["personalized_draft"] = draft
        except Exception as e:
            target["personalized_draft"] = f"Error generating: {str(e)}"
    return state

def outreach_decider_node(state: OutreachState) -> OutreachState:
    print("[Outreach Decider] Deciding action and final message...")
    system_prompt = load_prompt("outreach_prompt.txt")
    for target in state.get("targets", []):
        user_prompt = f"Profile: {json.dumps(target, indent=2)}\nDraft so far: {target.get('personalized_draft', '')}"
        try:
            decision_json = call_llm(system_prompt, user_prompt)
            target["outreach_decision"] = json.loads(decision_json) if decision_json.startswith("{") else {"action": "skip", "message": decision_json}
        except:
            target["outreach_decision"] = {"action": "skip", "message": "Error parsing decision"}
        
        # Log the decision (review mode - not sending)
        lead_id = state.get("supabase_lead_ids", {}).get(target["profile_url"])
        if lead_id:
            log_outreach(lead_id, target["outreach_decision"].get("action", "unknown"), 
                       target["outreach_decision"].get("message", ""))
        
        state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1
    return state

def conversational_node(state: OutreachState) -> OutreachState:
    print("[Conversational] Processing replies and conversations...")
    system_prompt = load_prompt("conversational_prompt.txt")
    # TODO: In real use, poll LinkedIn for new messages or integrate inbox
    # For now, placeholder logic
    for target in state.get("targets", []):
        # Example: if we had a reply, generate response
        if "reply_example" in target:  # placeholder
            user_prompt = f"Profile: {json.dumps(target)}\nRecent reply: {target.get('reply_example')}"
            try:
                reply = call_llm(system_prompt, user_prompt)
                # Save to conversation thread
                lead_id = state.get("supabase_lead_ids", {}).get(target["profile_url"])
                if lead_id:
                    thread = [{"role": "assistant", "content": reply}]
                    save_conversation(lead_id, thread)
            except Exception as e:
                print(f"Conversational error: {e}")
    return state

def build_graph():
    from langgraph.graph import StateGraph, END
    from src.state import OutreachState
    
    workflow = StateGraph(OutreachState)
    
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("scout", scout_node)
    workflow.add_node("personalizer", personalizer_node)
    workflow.add_node("outreach_decider", outreach_decider_node)
    workflow.add_node("conversational", conversational_node)
    
    workflow.set_entry_point("supervisor")
    
    # Main loop with conditional for review/pause
    def should_continue(state):
        if state.get("status") == "paused":
            return END
        return "scout"  # or add human review conditional here
    
    workflow.add_conditional_edges("supervisor", should_continue, {"scout": "scout", END: END})
    workflow.add_edge("scout", "personalizer")
    workflow.add_edge("personalizer", "outreach_decider")
    workflow.add_edge("outreach_decider", "conversational")
    workflow.add_edge("conversational", "supervisor")
    
    return workflow.compile()