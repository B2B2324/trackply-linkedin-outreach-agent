import time
import random
from src.llm import call_llm
from src.supabase_client import log_lead, log_outreach

class LinkedInOutreachAgent:
    def __init__(self, daily_cap: int = 75, review_mode: bool = True):
        self.daily_cap = daily_cap  # Conservative cap (user can do ~100 manually)
        self.review_mode = review_mode
        self.sent_today = 0

    def find_high_quality_leads(self, keywords: list[str] = None):
        """Find high-intent leads: Open to Work + AI freelancers."""
        if keywords is None:
            keywords = ["open to work", "prompt engineer", "ai evaluator", "data annotation", "rlhf", "freelance ai"]
        
        # TODO: Replace with real Apify LinkedIn Profile Search or browser scraping
        print("[LinkedIn] Searching for high-quality leads...")
        leads = [
            {
                "name": "Example AI Freelancer",
                "profile_url": "https://linkedin.com/in/example-ai-freelancer",
                "headline": "Open to Work | Prompt Engineer & AI Evaluator | Available for freelance RLHF",
                "location": "United States",
            }
        ]
        return leads

    def generate_message(self, lead: dict):
        system = """You are Stephen, founder of Trackply. 
Write in a natural, helpful, philosophy-first tone. 
Explain why Trackply is different (knowledge base, targeted search, Meta Agent, Kemba Job Coach, scam detection, gig tracking).
Gently steer towards trying Trackply without being pushy. Keep it short and human."""
        user = f"Profile: {lead}\nWrite a personalized LinkedIn message or connection note."
        return call_llm(system, user)

    def send_connection_or_dm(self, lead: dict, message: str):
        if self.review_mode:
            print(f"[LinkedIn - REVIEW] Would send to {lead['name']}: {message[:150]}...")
            return {"status": "review_pending", "lead": lead}
        
        # TODO: Add real browser automation or LinkedIn API here
        print(f"[LinkedIn] Sending to {lead['name']}...")
        time.sleep(random.randint(45, 120))  # Randomized delay
        
        # Always follow/connect
        print(f"[LinkedIn] Following/Connecting with {lead['name']}")
        
        log_outreach(lead.get("profile_url"), "connection_or_dm", message)
        self.sent_today += 1
        return {"status": "sent", "lead": lead}

    def run_daily_campaign(self, target_count: int = None):
        if target_count is None:
            target_count = self.daily_cap
        
        leads = self.find_high_quality_leads()
        
        for lead in leads[:target_count]:
            if self.sent_today >= self.daily_cap:
                print("[LinkedIn] Daily cap reached. Stopping.")
                break
            
            message = self.generate_message(lead)
            result = self.send_connection_or_dm(lead, message)
            
            if result["status"] == "sent":
                print(f"Sent to {lead['name']}")

if __name__ == "__main__":
    agent = LinkedInOutreachAgent(daily_cap=75, review_mode=True)
    agent.run_daily_campaign()