import argparse
from src.graph import build_graph
from src.state import OutreachState
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Run LinkedIn Outreach Agent")
    parser.add_argument("--mode", choices=["review", "live"], default="review", help="review = generate only, live = actually send (use with caution)")
    parser.add_argument("--campaign", default="default", help="Campaign name/ID")
    args = parser.parse_args()

    print(f"Starting LinkedIn Outreach Agent in {args.mode} mode...")

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
        "supabase_lead_ids": {}
    }

    # Run the graph
    result = app.invoke(initial_state)
    print("\nCampaign run complete.")
    print(f"Status: {result.get('status')}")
    print(f"Targets found: {len(result.get('targets', []))}")
    print(f"Messages sent today: {result.get('messages_sent_today')}")

if __name__ == "__main__":
    main()