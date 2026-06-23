import time
import random
from src.llm import call_llm
from src.supabase_client import log_outreach

class LinkedInOutreachAgent:
    def __init__(self, daily_cap: int = 75, review_mode: bool = True):
        self.daily_cap = daily_cap
        self.review_mode = review_mode
        self.sent_today = 0

    def find_high_quality_leads(self, keywords: list[str] = None):
        if keywords is None:
            keywords = ["open to work", "prompt engineer", "ai evaluator", "data annotation", "rlhf", "freelance ai"]
        
        print("[LinkedIn] Searching for high-quality leads (Open to Work + AI freelancers)...")
        # TODO: Replace with real Apify or browser search
        leads = [
            {
                "name": "Jordan Hale",
                "profile_url": "https://linkedin.com/in/jordan-hale-ai",
                "headline": "Open to Work | Prompt Engineer & AI Evaluator | Freelance RLHF",
                "location": "United States",
            }
        ]
        return leads

    def generate_message(self, lead: dict):
        """Generate natural but direct outreach for people we don't know."""
        system = """You are Stephen, founder of Trackply.
        Write in a natural, honest, and slightly direct tone.
        Since we don't know this person, it's okay to be somewhat open about why you're reaching out.
        Acknowledge that they're open to work.
        Gently invite them to try Trackply and use the feedback button.
        You can mention a promo code if it feels natural.
        Keep it short, human, and low-pressure."""
        
        user = f"""Profile: {lead}

        Write a LinkedIn connection note or message. Something like:
        "I see you're open to work... Please give Trackply a try and use the feedback button if you have suggestions."
        Make it sound like a real person, not a bot."""
        
        return call_llm(system, user)

    def send_connection_or_dm(self, lead: dict, message: str):
        if self.review_mode:
            print(f"[LinkedIn - REVIEW] Would send to {lead['name']}:\n{message}\n")
            return {"status": "review_pending", "lead": lead}

        print(f"[LinkedIn] Sending to {lead['name']}...")
        time.sleep(random.randint(45, 120))  # Randomized delay to look human

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