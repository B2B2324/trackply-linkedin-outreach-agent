from mcp_tools.tier_checker import check_tier_access

async def add_job_to_tracker(user_id: str, job_details: dict):
    if not check_tier_access(user_id, "add_job"):
        return {"error": "Quota exceeded. Please upgrade your Trackply plan."}
    
    # TODO: Call Trackply backend to add job
    return {
        "status": "success",
        "message": "Job added to your Trackply pipeline.",
        "job": job_details
    }

async def get_pipeline_summary(user_id: str):
    if not check_tier_access(user_id, "pipeline_summary"):
        return {"error": "Quota exceeded. Please upgrade your Trackply plan."}
    
    return {
        "status": "success",
        "summary": "You have 7 active applications. 2 need follow-up this week."
    }

async def check_scam_ghost_detector(user_id: str, job_url: str):
    if not check_tier_access(user_id, "scam_detector"):
        return {"error": "Quota exceeded. Please upgrade your Trackply plan."}
    
    return {
        "status": "success",
        "verdict": "Medium risk - Posting is 38 days old with no updates."
    }

# Add more tools as needed (update_application_status, etc.)