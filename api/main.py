"""
FastAPI server for the Trackply LinkedIn Outreach Agent.
Replaces Streamlit — exposes endpoints that the Agentic Labs dashboard calls.

Deploy on Railway. Set env vars:
  ANTHROPIC_API_KEY, SUPABASE_SERVICE_KEY, APIFY_TOKEN,
  LINKEDIN_LI_AT, LINKEDIN_JSESSIONID, LINKEDIN_CSRF_TOKEN,
  LINKEDIN_OWN_PROFILE_URL
"""
from __future__ import annotations

import io
import os
import sys
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Trackply Marketing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory run registry ────────────────────────────────────────────────────
_runs: dict[str, dict] = {}


class LiveCapture(io.TextIOBase):
    """Writes stdout lines to a list in real-time so callers can poll."""

    def __init__(self, log_list: list[str]):
        self._log = log_list

    def write(self, text: str) -> int:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                self._log.append(stripped)
        return len(text)

    def flush(self):
        pass


def _run_agent(run_id: str, review_mode: bool):
    run = _runs[run_id]
    run["status"] = "running"
    log: list[str] = run["log"]

    old_stdout = sys.stdout
    sys.stdout = LiveCapture(log)
    try:
        # Re-inject env vars at run time (Railway sets them at process start,
        # but we want to make sure they're available inside the agent modules).
        from src.nodes import build_graph
        from src.campaign_config import default_config as config

        config["review_mode"] = review_mode
        config["require_human_approval"] = review_mode
        config["daily_limit"] = 80
        config["weekly_connection_limit"] = 80

        initial_state = {
            "targets": [],
            "messages_sent_today": 0,
            "status": "active",
            "errors": [],
            "supabase_lead_ids": {},
        }
        graph = build_graph()
        final_state = graph.invoke(initial_state)

        sys.stdout = old_stdout

        leads = final_state.get("_leads_discovered", 0)
        errors = final_state.get("errors", [])
        send_log = final_state.get("_send_log", [])

        log.append("─" * 40)
        log.append(f"✓ Leads discovered: {leads}")
        for entry in send_log:
            ol = " [OpenLink]" if entry.get("ol") else ""
            log.append(f"  • {entry['name']} ({entry['rel']}{ol}) → {entry['action']} [{entry['result']}]")
        for e in errors:
            log.append(f"✗ {e}")
        if not send_log and not errors:
            log.append("No leads processed — see log above for details.")

        run["status"] = "completed"
        run["leads_found"] = leads
        run["errors"] = errors
        run["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as exc:
        sys.stdout = old_stdout
        log.append(f"✗ FATAL: {exc}")
        run["status"] = "failed"
        run["errors"] = [str(exc)]
        run["completed_at"] = datetime.now(timezone.utc).isoformat()


# ── Endpoints ─────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    review_mode: bool = True


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/runs/{run_id}/stop")
def stop_run(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    run["status"] = "failed"
    run["completed_at"] = datetime.now(timezone.utc).isoformat()
    run["log"].append("✗ Run stopped by user.")
    return {"ok": True}


@app.post("/run")
def start_run(body: RunRequest):
    run_id = uuid.uuid4().hex[:8]
    mode = "review" if body.review_mode else "LIVE"
    _runs[run_id] = {
        "id": run_id,
        "status": "starting",
        "review_mode": body.review_mode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "log": [f"[{mode}] Starting run…"],
        "leads_found": 0,
        "errors": [],
    }
    t = threading.Thread(target=_run_agent, args=(run_id, body.review_mode), daemon=True)
    t.start()
    return {"run_id": run_id}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/leads")
def get_leads():
    try:
        from src.supabase_client import _sb
        r = (
            _sb()
            .table("linkedin_leads")
            .select("name,headline,status,fit_score,date_sent,response_at,created_at,profile_url,relationship_type")
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        return r.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
def get_stats():
    try:
        from src.supabase_client import _sb, count_connection_requests_this_week
        sb = _sb()

        # Lead counts by status
        all_leads = sb.table("linkedin_leads").select("status", count="exact").execute()
        total = all_leads.count or 0

        sent = sb.table("linkedin_leads").select("id", count="exact").eq("status", "sent").execute().count or 0
        replied = sb.table("linkedin_leads").select("id", count="exact").eq("status", "replied").execute().count or 0
        discovered = sb.table("linkedin_leads").select("id", count="exact").eq("status", "discovered").execute().count or 0

        conn_used = count_connection_requests_this_week()

        # Activity last 30 days
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        activity_30d = sb.table("outreach_activity").select("id", count="exact").gte("created_at", cutoff).execute().count or 0
        total_activity = sb.table("outreach_activity").select("id", count="exact").execute().count or 0

        return {
            "total_leads": total,
            "discovered": discovered,
            "sent": sent,
            "replied": replied,
            "connection_requests_this_week": conn_used,
            "weekly_limit": 80,
            "total_activity": total_activity,
            "activity_last_30d": activity_30d,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/activity")
def get_activity():
    try:
        from src.supabase_client import _sb
        r = (
            _sb()
            .table("outreach_activity")
            .select("agent,action,target,result,created_at,metadata")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return r.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
