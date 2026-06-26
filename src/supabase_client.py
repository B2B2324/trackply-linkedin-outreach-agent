from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

url: str = os.environ.get("SUPABASE_URL", "https://vglfaviliadxevfillbb.supabase.co")
key: str = os.environ.get(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZnbGZhdmlsaWFkeGV2ZmlsbGJiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODUyMjgyOSwiZXhwIjoyMDk0MDk4ODI5fQ.Q-UmRrn559HZCDt9cm_i4K3HJFM0qD7an5kDjFazkko",
)
supabase: Client = create_client(url, key)


# ── linkedin_leads ────────────────────────────────────────────────────────────

def log_lead(profile: dict) -> dict | None:
    """Upsert a discovered LinkedIn profile into linkedin_leads."""
    data = {
        "profile_url":   profile.get("profile_url"),
        "name":          profile.get("name"),
        "headline":      profile.get("headline"),
        "location":      profile.get("location"),
        "fit_score":     profile.get("fit_score"),
        "why_qualified": profile.get("why_qualified"),
        "status":        profile.get("status", "discovered"),
    }
    response = supabase.table("linkedin_leads").upsert(data, on_conflict="profile_url").execute()
    _log_activity("linkedin", "lead_discovered", profile.get("profile_url"), "success", {
        "name": profile.get("name"), "fit_score": profile.get("fit_score")
    })
    return response.data[0] if response.data else None


def update_lead_status(profile_url: str, status: str, note: str = None) -> None:
    """Update the status (and optional note) on an existing lead."""
    update = {"status": status}
    if note:
        update["note"] = note
    supabase.table("linkedin_leads").update(update).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", status, profile_url, "success")


def mark_lead_sent(profile_url: str, message: str) -> None:
    """Record that an outreach message was sent."""
    from datetime import datetime, timezone
    supabase.table("linkedin_leads").update({
        "status":    "sent",
        "note":      message[:500] if message else None,
        "date_sent": datetime.now(timezone.utc).isoformat(),
    }).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", "message_sent", profile_url, "success", {"message_len": len(message or "")})


def record_reply(profile_url: str, reply_text: str) -> None:
    """Record an inbound reply from a lead."""
    from datetime import datetime, timezone
    supabase.table("linkedin_leads").update({
        "status":      "replied",
        "response":    reply_text[:1000] if reply_text else None,
        "response_at": datetime.now(timezone.utc).isoformat(),
    }).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", "reply_received", profile_url, "success")


# ── outreach_activity (general audit log) ────────────────────────────────────

def _log_activity(agent: str, action: str, target: str = None,
                  result: str = "success", metadata: dict = None) -> None:
    """Append one row to outreach_activity. Silently swallows errors."""
    try:
        supabase.table("outreach_activity").insert({
            "agent":    agent,
            "action":   action,
            "target":   target,
            "result":   result,
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        print(f"[supabase_client] activity log error: {e}")


def log_activity(agent: str, action: str, target: str = None,
                 result: str = "success", metadata: dict = None) -> None:
    """Public wrapper for _log_activity — call this from any agent."""
    _log_activity(agent, action, target, result, metadata)


# ── legacy helpers (kept for compatibility with approval_queue, nodes) ────────

def log_outreach(lead_id: str, action: str, message: str, outcome: str = "pending") -> None:
    _log_activity("linkedin", action, lead_id, outcome, {"message": message[:200] if message else None})


def get_conversation(lead_id: str) -> dict | None:
    response = supabase.table("conversations").select("*").eq("lead_id", lead_id).execute()
    return response.data[0] if response.data else None


def save_conversation(lead_id: str, thread: list) -> None:
    supabase.table("conversations").upsert({"lead_id": lead_id, "thread": thread}).execute()
