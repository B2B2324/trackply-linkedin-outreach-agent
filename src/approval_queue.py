from src.supabase_client import supabase

def add_to_approval_queue(lead_id: str, action: str, message: str, profile_data: dict):
    """Add an outreach item that requires human review."""
    data = {
        "lead_id": lead_id,
        "action": action,
        "proposed_message": message,
        "profile_data": profile_data,
        "status": "pending_review",
        "created_at": "now()"
    }
    response = supabase.table("approval_queue").insert(data).execute()
    return response.data

def get_pending_reviews():
    """Fetch items waiting for human approval."""
    response = supabase.table("approval_queue").select("*").eq("status", "pending_review").execute()
    return response.data or []

def approve_item(queue_id: str, approved: bool = True, final_message: str = None):
    """Approve or reject an item. If approved, optionally update message."""
    update_data = {"status": "approved" if approved else "rejected"}
    if final_message:
        update_data["final_message"] = final_message
    supabase.table("approval_queue").update(update_data).eq("id", queue_id).execute()
    # TODO: If approved, trigger actual send via browser/API
    print(f"Item {queue_id} {'approved' if approved else 'rejected'}")