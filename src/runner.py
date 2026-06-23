import argparse
from src.graph import build_graph
from src.state import OutreachState
from datetime import datetime

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["review", "live"], default="review")
    parser.add_argument("--campaign", default="default-campaign")
    args = parser.parse_args()

    print(f"=== Trackply LinkedIn Outreach Agent ===")
    print(f"Mode: {args.mode} | Campaign: {args.campaign}")

    app = build_graph()
    initial_state: OutreachState = {
        "campaign_id": args.campaign,
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "targets": [],
        "current_index": 0,
        "messages_sent_today": 0,
        "replies_received": 0,
        "conversations": {},
        "errors": [],
        "status": "running",
        "last_action_at": None,
        "supabase_lead_ids": {},
        "human_approval_required": True
    }

    result = app.invoke(initial_state)
    print("\nRun complete.")
    print(f"Status: {result.get('status')}")
    print(f"Targets processed: {len(result.get('targets', []))}")
    print(f"Messages/decisions generated: {result.get('messages_sent_today')}")
    if result.get("errors"):
        print(f"Errors: {result['errors']}")