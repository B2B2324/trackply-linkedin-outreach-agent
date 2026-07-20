"""
One-shot local send test — the decisive IP experiment.

Sends a SINGLE real connection request from THIS machine's IP using the local
voyager sender, bypassing Apify entirely. Run it from the same machine/browser
where you can manually send LinkedIn connection requests.

  200/201  → LinkedIn accepts writes from your home IP. The 401s were caused
             by the cloud egress IP (Railway/Apify), not the code or account.
             Fix = run the send path locally (SENDER_MODE=local) or route Apify
             through a residential IP that LinkedIn trusts.
  401      → writes are refused from your IP too. Then it is NOT an IP problem;
             it is account- or session-level, and no proxy change will help.

Usage:
    # put LinkedIn cookies in .env (see LOCAL_SEND.md), then:
    python test_local_send.py https://www.linkedin.com/in/<someone>

Nothing is written to Supabase; this only exercises the send call and prints
the raw result.
"""
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # dotenv optional; env vars may already be exported

from src.local_sender import local_live_send

DEFAULT_NOTE = ""  # empty note = plain connect; safest for a test


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_local_send.py <linkedin_profile_url> [note]")
        sys.exit(1)
    profile_url = sys.argv[1]
    note = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_NOTE

    for var in ("LINKEDIN_LI_AT", "LINKEDIN_JSESSIONID"):
        if not os.environ.get(var):
            print(f"[!] {var} not set. Copy it from Railway into your .env first.")
            sys.exit(1)

    print(f"Sending connection_request → {profile_url} from LOCAL IP ...")
    result = local_live_send("connection_request", profile_url, note, {})
    print("\n=== RESULT ===")
    print(f"success     : {result.get('success')}")
    print(f"status_code : {result.get('status_code')}")
    print(f"detail      : {result.get('detail')}")

    if result.get("success"):
        print("\n>>> WRITES WORK FROM YOUR IP. It was the cloud egress IP all along.")
    else:
        print("\n>>> Still rejected from your own IP. Not an IP problem — "
              "investigate account/session, not the proxy.")


if __name__ == "__main__":
    main()
