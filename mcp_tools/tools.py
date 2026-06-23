from mcp_tools.tier_checker import check_tier_access

# Core user-facing MCP tools for Claude / Grok / ChatGPT

async def add_job_to_tracker(user_id: str, job_url: str = None, job_details: dict = None):
    if not check_tier_access(user_id, "add_job"):
        return {"error": "Quota exceeded. Upgrade your Trackply plan."}
    
    # TODO: Integrate with actual Trackply backend
    return {
        "status": "success",
        "message": "Job added to your Trackply pipeline.",
        "job_url": job_url
    }

async def get_pipeline_summary(user_id: str):
    if not check_tier_access(user_id, "pipeline_summary"):
        return {"error": "Quota exceeded. Upgrade your Trackply plan."}
    
    return {
        "status": "success",
        "summary": "You currently have 7 active applications. 3 need follow-up this week."
    }

async def check_scam_ghost_detector(user_id: str, job_url: str):
    if not check_tier_access(user_id, "scam_detector"):
        return {"error": "Quota exceeded. Upgrade your Trackply plan."}
    
    return {
        "status": "success",
        "verdict": "Medium risk - Job has been posted for 38 days with no updates.",
        "recommendation": "Consider applying with caution or look for fresher postings."
    }

async def update_application_status(user_id: str, job_id: str, new_status: str, notes: str = ""):
    if not check_tier_access(user_id, "update_status"):
        return {"error": "Quota exceeded. Upgrade your Trackply plan."}
    
    return {
        "status": "success",
        "message": f"Updated job {job_id} to status: {new_status}"
    }

async def get_kemba_advice(user_id: str, question: str):
    if not check_tier_access(user_id, "kemba_advice"):
        return {"error": "Quota exceeded. Upgrade your Trackply plan."}
    
    # This can later call the actual Kemba / Job Coach agent
    return {
        "status": "success",
        "advice": "Based on your current applications, I recommend focusing on roles that value prompt engineering experience."
    }