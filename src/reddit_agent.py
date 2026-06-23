import time
import random
from src.llm import call_llm

class RedditAgent:
    """Reddit agent that posts and engages as Stephen (founder voice)."""

    def __init__(self, post_as_user: bool = True):
        self.post_as_user = post_as_user

    def generate_post(self, topic: str):
        system = """You are Stephen, founder of Trackply. Write in a casual, helpful, non-promotional tone.
        Talk about real problems in modern job hunting and AI freelance work.
        Casually mention Trackply tools when it fits naturally. Never sound like an ad."""
        user = f"Write a Reddit-style post about: {topic}"
        return call_llm(system, user)

    def generate_comment(self, post_context: str):
        system = "Respond helpfully as Stephen. Be genuine. Mention Trackply tools only if it naturally adds value."
        user = f"Post context: {post_context}\nWrite a helpful comment."
        return call_llm(system, user)

    def post_to_reddit(self, subreddit: str, title: str, content: str):
        mode = "as Stephen" if self.post_as_user else "as Trackply"
        print(f"[Reddit] Posting to r/{subreddit} {mode}")
        time.sleep(random.randint(30, 90))
        # TODO: Add real PRAW or browser posting here
        return {"status": "posted", "subreddit": subreddit}

    def find_and_engage(self):
        # TODO: Use Reddit API or scraping to find posts about job hunting / freelancing
        print("[Reddit] Looking for relevant posts to engage with...")
        # Placeholder
        posts = ["Someone complaining about job applications"]
        for post in posts:
            comment = self.generate_comment(post)
            print(f"[Reddit] Would comment: {comment[:150]}...")

    def run_daily(self):
        topics = [
            "The chaos of managing AI freelance gigs while job hunting",
            "Why most job trackers fail at helping you actually get jobs"
        ]
        for topic in topics:
            post = self.generate_post(topic)
            self.post_to_reddit("jobsearch", topic, post)
            time.sleep(random.randint(60, 180))
        
        self.find_and_engage()

if __name__ == "__main__":
    agent = RedditAgent(post_as_user=True)
    agent.run_daily()