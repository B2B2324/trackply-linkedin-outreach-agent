from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def log_lead(profile: dict):
    """Insert or update a lead in Supabase."""
    data = {
        "profile_url": profile.get("profile_url"),
        "name": profile.get("name"),
        "headline": profile.get("headline"),
        "location": profile.get("location"),
        "fit_score": profile.get("fit_score"),
        "why_qualified": profile.get("why_qualified"),
    }
    response = supabase.table("linkedin_leads").upsert(data, on_conflict="profile_url").execute()
    return response.data[0] if response.data else None

def log_outreach(lead_id: str, action: str, message: str, outcome: str = "pending"):
    data = {
        "lead_id": lead_id,
        "action": action,
        "message": message,
        "outcome": outcome
    }
    supabase.table("outreach_logs").insert(data).execute()

def get_conversation(lead_id: str):
    response = supabase.table("conversations").select("*").eq("lead_id", lead_id).execute()
    return response.data[0] if response.data else None

def save_conversation(lead_id: str, thread: list):
    supabase.table("conversations").upsert({"lead_id": lead_id, "thread": thread}).execute()