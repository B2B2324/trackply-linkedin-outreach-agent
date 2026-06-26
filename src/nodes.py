from __future__ import annotations

import json

from src.state import OutreachState
from src.llm import call_llm
from src.supabase_client import (
    log_lead, log_outreach, save_conversation,
    update_lead_status, mark_lead_sent, record_reply, log_activity,
    count_connection_requests_this_week,
)
from src.prompts import load_prompt
from src.utils import human_like_delay
from src.campaign_config import load_campaign_config

config = load_campaign_config()

# ── Priority order for outreach ───────────────────────────────────────────────
# 1st degree  → DM immediately, always available
# open_link   → free DM without connecting (like InMail), always available
# 2nd degree  → connection request (burns weekly quota)
# unknown     → treat as 2nd degree (optimistic)
# 3rd degree  → connection request only if quota allows; skip otherwise
_RELATIONSHIP_PRIORITY = {"1st": 0, "open_link": 1, "2nd": 2, "unknown": 3, "3rd": 4}


def _can_dm_without_connecting(target: dict) -> bool:
    """Returns True if we can send a message without using a connection request."""
    rel = target.get("relationship_type", "unknown")
    return rel == "1st" or target.get("is_open_link", False)


def _choose_action(target: dict, conn_limit_reached: bool) -> str:
    """
    Determine the outreach action for a single target.

    Priority rules:
    - 1st degree            → 'dm'               (always)
    - open_link             → 'dm'               (always — no connect needed)
    - 2nd/unknown + budget  → 'connection_request'
    - 2nd/unknown + no bud  → 'skip'  (can't DM and can't connect)
    - 3rd + budget          → 'connection_request' (lower priority, still try)
    - 3rd + no budget       → 'skip'
    """
    rel = target.get("relationship_type", "unknown")

    if rel == "1st" or target.get("is_open_link", False):
        return "dm"

    if conn_limit_reached:
        return "skip"

    # 2nd, unknown, 3rd — use a connection request if quota allows
    return "connection_request"


# ── Nodes ─────────────────────────────────────────────────────────────────────

def supervisor_node(state: OutreachState) -> OutreachState:
    """Check daily message limit and weekly connection request budget."""
    print("[Supervisor] Checking limits...")

    if state.get("messages_sent_today", 0) >= config["daily_limit"]:
        state["status"] = "paused"
        print(f"[Supervisor] Daily limit of {config['daily_limit']} reached.")
        return state

    # Hydrate weekly connection count from Supabase if not already in state
    if "connection_requests_this_week" not in state:
        state["connection_requests_this_week"] = count_connection_requests_this_week()

    weekly_limit = config.get("weekly_connection_limit", 20)
    used = state["connection_requests_this_week"]
    remaining = max(0, weekly_limit - used)
    print(f"[Supervisor] Connection requests this week: {used}/{weekly_limit} ({remaining} remaining)")

    if remaining == 0:
        print("[Supervisor] Weekly connection limit reached — will DM 1st-degree and OpenLink only.")

    state["status"] = "active"
    return state


def scout_node(state: OutreachState) -> OutreachState:
    """
    Discover and prioritise leads.

    Targets are sorted so that 1st-degree and OpenLink profiles come first
    (they never consume the connection budget), then 2nd, then 3rd.
    In a real integration Apify would populate relationship_type/is_open_link
    from the profile page.  The mock data below exercises all paths.
    """
    print("[Scout] Discovering and prioritising leads...")

    if not state.get("targets"):
        # Mock targets covering every relationship scenario
        state["targets"] = [
            {
                "name": "Alex Rivera",
                "profile_url": "https://www.linkedin.com/in/alex-rivera-ai",
                "headline": "AI Evaluator @ Outlier | Open to Work | Prompt Engineering",
                "location": "United States",
                "about_snippet": "Freelancing on AI evaluation platforms. Looking for better tools to track gigs.",
                "fit_score": 9.5,
                "why_qualified": "Active AI evaluator actively looking — ideal Trackply user.",
                "recent_activity_keywords": ["AI", "evaluation", "open to work"],
                "relationship_type": "1st",   # already connected → DM
                "is_open_link": False,
            },
            {
                "name": "Sam Park",
                "profile_url": "https://www.linkedin.com/in/sam-park-rlhf",
                "headline": "RLHF Contractor | Prompt Engineer | Job Seeking",
                "location": "Canada",
                "about_snippet": "Doing RLHF work on multiple platforms simultaneously — hard to track.",
                "fit_score": 8.8,
                "why_qualified": "Multi-platform gig worker — Trackply's core use-case.",
                "recent_activity_keywords": ["RLHF", "freelance", "job search"],
                "relationship_type": "2nd",   # in network → connection request
                "is_open_link": False,
            },
            {
                "name": "Jordan Hale",
                "profile_url": "https://www.linkedin.com/in/jordan-hale-open",
                "headline": "Open to Work | AI Data Annotator",
                "location": "United States",
                "about_snippet": "Switched on OpenLink so anyone can message me.",
                "fit_score": 8.2,
                "why_qualified": "OpenLink enabled — free DM without connecting.",
                "recent_activity_keywords": ["annotation", "open to work"],
                "relationship_type": "3rd",
                "is_open_link": True,          # OpenLink → DM even though 3rd degree
            },
            {
                "name": "Casey Morgan",
                "profile_url": "https://www.linkedin.com/in/casey-morgan-ml",
                "headline": "ML Freelancer | Looking for contracts",
                "location": "United Kingdom",
                "about_snippet": "Hard to reach — 3rd degree, no OpenLink.",
                "fit_score": 6.5,
                "why_qualified": "Decent fit but hard to reach.",
                "recent_activity_keywords": ["ML", "freelance"],
                "relationship_type": "3rd",
                "is_open_link": False,         # 3rd + no OpenLink → needs budget
            },
        ]

    # Sort by priority: 1st/OpenLink → 2nd/unknown → 3rd
    def sort_key(t: dict) -> int:
        if t.get("relationship_type") == "1st" or t.get("is_open_link"):
            return 0
        return _RELATIONSHIP_PRIORITY.get(t.get("relationship_type", "unknown"), 99)

    state["targets"] = sorted(state["targets"], key=sort_key)

    for t in state["targets"]:
        try:
            lead = log_lead({**t, "relationship_type": t.get("relationship_type", "unknown"),
                             "is_open_link": t.get("is_open_link", False)})
            if lead:
                state.setdefault("supabase_lead_ids", {})[t["profile_url"]] = lead.get("id")
        except Exception as e:
            state.setdefault("errors", []).append(f"Scout log error: {e}")

    print(f"[Scout] {len(state['targets'])} leads queued (sorted by reachability)")
    return state


def personalizer_node(state: OutreachState) -> OutreachState:
    """Generate personalised drafts, skipping leads that will be skipped anyway."""
    print("[Personalizer] Generating personalised drafts...")

    conn_limit_reached = (
        state.get("connection_requests_this_week", 0) >= config.get("weekly_connection_limit", 20)
    )
    system_prompt = load_prompt("personalizer_prompt.txt")

    for target in state.get("targets", []):
        action = _choose_action(target, conn_limit_reached)
        if action == "skip":
            target["personalized_draft"] = ""
            target["_skip_reason"] = "connection limit reached and not DM-able"
            continue

        try:
            context = {
                "profile": target,
                "outreach_type": "dm" if action == "dm" else "connection_request",
                "is_open_link": target.get("is_open_link", False),
                "relationship": target.get("relationship_type", "unknown"),
            }
            draft = call_llm(system_prompt, f"Profile data:\n{json.dumps(context, indent=2)}")
            target["personalized_draft"] = draft
        except Exception as e:
            target["personalized_draft"] = ""
            state.setdefault("errors", []).append(str(e))

    return state


def outreach_decider_node(state: OutreachState) -> OutreachState:
    """
    Decide final action per lead and log to Supabase.

    Routing:
      1st degree  → dm        (always)
      open_link   → dm        (always)
      2nd/unknown → connection_request  if budget remains
      3rd degree  → connection_request  if budget remains
      any         → skip      if limit reached and not DM-able
    """
    print("[Outreach Decider] Routing leads by relationship type and connection budget...")

    system_prompt = load_prompt("outreach_prompt.txt")
    weekly_limit = config.get("weekly_connection_limit", 20)
    conn_used = state.get("connection_requests_this_week", 0)

    for target in state.get("targets", []):
        try:
            conn_limit_reached = conn_used >= weekly_limit
            action = _choose_action(target, conn_limit_reached)

            if action == "skip":
                reason = target.get("_skip_reason", "connection limit reached")
                print(f"  [skip] {target.get('name')} — {reason}")
                log_activity(
                    "linkedin", "skipped", target.get("profile_url"),
                    result="skipped",
                    metadata={"reason": reason, "relationship": target.get("relationship_type")},
                )
                target["outreach_decision"] = {"action": "skip", "reason": reason}
                continue

            # Ask LLM to craft the exact message for the chosen action type
            draft = target.get("personalized_draft", "")
            user_prompt = (
                f"Profile: {json.dumps(target)}\n"
                f"Required action: {action}\n"
                f"Draft: {draft}"
            )
            decision_str = call_llm(system_prompt, user_prompt)
            try:
                decision = json.loads(decision_str) if decision_str.strip().startswith("{") else {}
            except json.JSONDecodeError:
                decision = {}

            # Override action — LLM cannot override our routing logic
            decision["action"] = action
            decision.setdefault("message", draft[:300] if draft else "")
            target["outreach_decision"] = decision

            profile_url = target.get("profile_url")
            lead_id = state.get("supabase_lead_ids", {}).get(profile_url)
            message = decision.get("message", "")

            if config.get("require_human_approval"):
                # Review mode — draft saved, human approves before send
                try:
                    from src.approval_queue import add_to_approval_queue
                    add_to_approval_queue(lead_id, action, message, target)
                except Exception:
                    pass
                update_lead_status(profile_url, "message_drafted", note=message[:500])
                log_activity(
                    "linkedin", "approval_requested", profile_url, "pending",
                    metadata={"action": action, "relationship": target.get("relationship_type"),
                              "is_open_link": target.get("is_open_link", False)},
                )
                print(f"  [drafted] {target.get('name')} → {action} (awaiting approval)")
            else:
                mark_lead_sent(profile_url, message)
                log_outreach(lead_id or "unknown", action, message)
                if action == "connection_request":
                    log_activity(
                        "linkedin", "connection_request_sent", profile_url, "success",
                        metadata={"relationship": target.get("relationship_type")},
                    )
                    conn_used += 1
                    state["connection_requests_this_week"] = conn_used
                print(f"  [sent] {target.get('name')} → {action}")

            state["messages_sent_today"] = state.get("messages_sent_today", 0) + 1

            if config.get("min_delay_seconds") and not config.get("review_mode"):
                human_like_delay(
                    config["min_delay_seconds"],
                    config.get("max_delay_seconds", 120),
                )

        except Exception as e:
            state.setdefault("errors", []).append(f"Outreach error for {target.get('name')}: {e}")

    return state


def conversational_node(state: OutreachState) -> OutreachState:
    """Handle inbound replies from 1st-degree connections."""
    print("[Conversational] Checking for replies...")
    system_prompt = load_prompt("conversational_prompt.txt")

    for target in state.get("targets", []):
        if not target.get("has_new_reply"):
            continue
        try:
            user_prompt = (
                f"Profile: {json.dumps(target)}\n"
                f"New reply: {target.get('new_reply_content', '')}"
            )
            reply = call_llm(system_prompt, user_prompt)
            lead_id = state.get("supabase_lead_ids", {}).get(target.get("profile_url"))
            if lead_id:
                thread = [
                    {"from": "lead", "content": target.get("new_reply_content")},
                    {"from": "assistant", "content": reply},
                ]
                save_conversation(lead_id, thread)
            record_reply(target.get("profile_url"), target.get("new_reply_content", ""))
            target["generated_reply"] = reply
        except Exception as e:
            state.setdefault("errors", []).append(str(e))

    return state


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph():
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(OutreachState)
    workflow.add_node("supervisor",        supervisor_node)
    workflow.add_node("scout",             scout_node)
    workflow.add_node("personalizer",      personalizer_node)
    workflow.add_node("outreach_decider",  outreach_decider_node)
    workflow.add_node("conversational",    conversational_node)

    workflow.set_entry_point("supervisor")

    def route_after_supervisor(state: OutreachState):
        return END if state.get("status") == "paused" else "scout"

    workflow.add_conditional_edges("supervisor", route_after_supervisor)
    workflow.add_edge("scout",            "personalizer")
    workflow.add_edge("personalizer",     "outreach_decider")
    workflow.add_edge("outreach_decider", "conversational")
    workflow.add_edge("conversational",   "supervisor")

    return workflow.compile()
