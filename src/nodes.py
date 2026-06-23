from src.state import OutreachState
from src.llm import call_llm
from src.supabase_client import log_lead, log_outreach, save_conversation
from src.prompts import load_prompt
from src.utils import human_like_delay
from src.error_handler import safe_execute, retry_with_backoff
from src.campaign_config import load_campaign_config
import json

config = load_campaign_config()

def supervisor_node(state: OutreachState) -> OutreachState:
    print("[Supervisor] Checking limits and status...")
    if state.get("messages_sent_today", 0) >= config["daily_limit"]:
        state["status"] = "paused"
        print(f"[Supervisor] Daily limit of {config['daily_limit']} reached.")
    return state

def scout_node(state: OutreachState) -> OutreachState:
    print("[Scout] Discovering high-intent profiles...")
    # TODO: Real Apify integration here
    if not state.get("targets"):
        state["targets"] = [{
            "name": "Jordan Hale",
            "profile_url": "https://www.linkedin.com/in/jordan-hale-ai",
            "headline": "Open to Work | AI Data Annotator & Prompt Engineer | Freelance RLHF",
            "location": "United States",
            "about_snippet": "Currently doing AI evaluation work on Outlier and Mercor. Looking for more stable opportunities or better tools to manage gigs.",
            "fit_score": 9.0,
            "why_qualified": "Ideal for Trackply gig tracker + targeted applications.",
            "recent_activity_keywords": ["AI", "evaluation", "freelance", "job search"]
        }]
    for t in state.get("targets", []):
        try:
            lead = log_lead(t)
            if lead:
                state.setdefault("supabase_lead_ids", {})[t["profile_url"]] = lead.get("id")
        except Exception as e:
            state.setdefault("errors", []).append(f"Scout log error: {e}")
    return state

def personalizer_node(state: OutreachState) -> OutreachState:
    print("[Personalizer] Generating personalized content with LLM...")
    system_prompt = load_prompt("personalizer_prompt.txt")
    for target in state.get("targets", []):
        try:
            user_prompt = f"Profile data: {json.dumps(target, indent=2)}"
            draft = call_llm(system_prompt, user_prompt)
            target["personalized_draft"] = draft
        except Exception as e:
            target["personalized_draft"] = f"Generation failed: {str(e)}"
            state.setdefault("errors", []).append(str(e))
    return state

def outreach_decider_node(state: OutreachState) -> OutreachState:
    print("[Outreach Decider] LLM deciding action and message...")
    system_prompt = load_prompt("outreach_prompt.txt")
    for target in state.get("targets", []):
        try:
            user_prompt = f"Profile: {json.dumps(target)}\nDraft: {target.get('personalized_draft', '')}"
            decision_str = call_llm(system_prompt, user_prompt)
            decision = json.loads(decision_str) if decision_str.strip().startswith("{") else {"action": "skip", "message": decision_str}
            target["outreach_decision"] = decision
            
            lead_id = state.get("supabase_lead_ids", {}).get(target.get("profile_url"))
            if lead_id and config.get("require_human_approval"):
                from src.approval_queue import add_to_approval_queue
                add_to_approval_queue(lead_id, decision.get("action"), decision.get("message"), target)
            else:
                log_outreach(lead_id or "unknown", decision.get("action"), decision.get("message"))
            
            state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1
            if config.get("min_delay_seconds"):
                human_like_delay(config["min_delay_seconds"], config.get("max_delay_seconds", 120))
        except Exception as e:
            state.setdefault("errors", []).append(f"Outreach error: {e}")
    return state

def conversational_node(state: OutreachState) -> OutreachState:
    print("[Conversational] Handling replies with LLM...")
    system_prompt = load_prompt("conversational_prompt.txt")
    for target in state.get("targets", []):
        if target.get("has_new_reply"):  # In real use, detect new messages
            try:
                user_prompt = f"Profile: {json.dumps(target)}\nNew reply: {target.get('new_reply_content', 'Hello')}"
                reply = call_llm(system_prompt, user_prompt)
                lead_id = state.get("supabase_lead_ids", {}).get(target.get("profile_url"))
                if lead_id:
                    thread = [{"from": "user", "content": target.get('new_reply_content')}, {"from": "assistant", "content": reply}]
                    save_conversation(lead_id, thread)
                target["generated_reply"] = reply
            except Exception as e:
                state.setdefault("errors", []).append(str(e))
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
    
    def route_after_supervisor(state):
        if state.get("status") == "paused":
            return END
        return "scout"
    
    workflow.add_conditional_edges("supervisor", route_after_supervisor)
    workflow.add_edge("scout", "personalizer")
    workflow.add_edge("personalizer", "outreach_decider")
    workflow.add_edge("outreach_decider", "conversational")
    workflow.add_edge("conversational", "supervisor")
    
    return workflow.compile()