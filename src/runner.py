import argparse
from datetime import datetime
from src.graph import build_graph
from src.state import OutreachState

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Outreach Agent")
    parser.add_argument("--mode", choices=["review", "live"], default="review",
                        help="review = generate only (safe), live = actually send")
    parser.add_argument("--campaign", default="default", help="Campaign name")
    args = parser.parse_args()

    print("=== Trackply LinkedIn Outreach Agent ===")
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
    }

    result = app.invoke(initial_state)

    print("\n=== Run Complete ===")
    print(f"Status: {result.get('status')}")
    print(f"Targets processed: {len(result.get('targets', []))}")
    print(f"Messages/Decisions: {result.get('messages_sent_today')}")

    if result.get("errors"):
        print(f"Errors: {result['errors']}")

if __name__ == "__main__":
    main()