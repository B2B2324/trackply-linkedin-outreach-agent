from __future__ import annotations
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

_SUPABASE_URL = "https://vglfaviliadxevfillbb.supabase.co"


def _sb() -> Client:
    """
    Return a Supabase client built from the current environment variables.
    Called fresh on every DB operation so env vars injected at button-click
    time (dashboard sets SUPABASE_KEY before the graph runs) are always used.
    """
    url = os.environ.get("SUPABASE_URL", _SUPABASE_URL)
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not key:
        raise RuntimeError(
            "SUPABASE_KEY / SUPABASE_SERVICE_KEY not set — "
            "add it to Streamlit secrets as SUPABASE_SERVICE_KEY"
        )
    return create_client(url, key)


# Keep a module-level alias so reddit_sender.py (and any legacy callers)
# that do `from src.supabase_client import supabase` still compile.
# They'll get a fresh client on first attribute access via __getattr__ below.
# Actual DB calls should use _sb() directly.
class _LazyClient:
    """Proxy that forwards attribute access to a freshly-created client."""
    def __getattr__(self, name):
        return getattr(_sb(), name)

supabase = _LazyClient()   # type: ignore[assignment]


# ── linkedin_leads ────────────────────────────────────────────────────────────

def count_connection_requests_this_week() -> int:
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        r = (_sb().table("outreach_activity")
             .select("*", count="exact", head=True)
             .eq("action", "connection_request_sent")
             .gte("created_at", cutoff)
             .execute())
        return r.count or 0
    except Exception as e:
        print(f"[supabase_client] count_connection_requests_this_week error: {e}")
        return 0


def log_lead(profile: dict) -> dict | None:
    """Upsert a discovered LinkedIn profile into linkedin_leads."""
    data = {
        "profile_url":       profile.get("profile_url"),
        "name":              profile.get("name"),
        "headline":          profile.get("headline"),
        "location":          profile.get("location"),
        "fit_score":         profile.get("fit_score"),
        "why_qualified":     profile.get("why_qualified"),
        "status":            profile.get("status", "discovered"),
        "relationship_type": profile.get("relationship_type", "unknown"),
        "is_open_link":      bool(profile.get("is_open_link", False)),
    }
    response = _sb().table("linkedin_leads").upsert(data, on_conflict="profile_url").execute()
    _log_activity("linkedin", "lead_discovered", profile.get("profile_url"), "success", {
        "name": profile.get("name"), "fit_score": profile.get("fit_score")
    })
    return response.data[0] if response.data else None


def update_lead_status(profile_url: str, status: str, note: str = None) -> None:
    update = {"status": status}
    if note:
        update["note"] = note
    _sb().table("linkedin_leads").update(update).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", status, profile_url, "success")


def mark_lead_sent(profile_url: str, message: str) -> None:
    from datetime import datetime, timezone
    _sb().table("linkedin_leads").update({
        "status":    "sent",
        "note":      message[:500] if message else None,
        "date_sent": datetime.now(timezone.utc).isoformat(),
    }).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", "message_sent", profile_url, "success", {"message_len": len(message or "")})


def record_reply(profile_url: str, reply_text: str) -> None:
    from datetime import datetime, timezone
    _sb().table("linkedin_leads").update({
        "status":      "replied",
        "response":    reply_text[:1000] if reply_text else None,
        "response_at": datetime.now(timezone.utc).isoformat(),
    }).eq("profile_url", profile_url).execute()
    _log_activity("linkedin", "reply_received", profile_url, "success")


# ── outreach_activity ─────────────────────────────────────────────────────────

def _log_activity(agent: str, action: str, target: str = None,
                  result: str = "success", metadata: dict = None) -> None:
    try:
        _sb().table("outreach_activity").insert({
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
    _log_activity(agent, action, target, result, metadata)


# ── legacy helpers ────────────────────────────────────────────────────────────

def log_outreach(lead_id: str, action: str, message: str, outcome: str = "pending") -> None:
    _log_activity("linkedin", action, lead_id, outcome, {"message": message[:200] if message else None})


def get_conversation(lead_id: str) -> dict | None:
    response = _sb().table("conversations").select("*").eq("lead_id", lead_id).execute()
    return response.data[0] if response.data else None


def save_conversation(lead_id: str, thread: list) -> None:
    _sb().table("conversations").upsert({"lead_id": lead_id, "thread": thread}).execute()
