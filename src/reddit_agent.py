from src.llm import call_llm
from src.prompts import load_prompt

# Reddit Agent for Trackply
# Posts as you (the founder) until subreddit karma builds up

class RedditAgent:
    def __init__(self, post_as_user=True):
        self.post_as_user = post_as_user  # True = post as Stephen until karma is high
        
    def generate_content(self, topic: str):
        system = load_prompt("seo_writer_prompt.txt") or "You are a helpful founder sharing real job search advice."
        user = f"Write a natural Reddit-style post or comment about: {topic}. Keep it authentic, helpful, and lightly mention Trackply if it fits naturally."
        return call_llm(system, user)
    
    def post_to_reddit(self, subreddit: str, title: str, content: str):
        if self.post_as_user:
            print(f"[Reddit] Posting as founder to r/{subreddit} (manual approval recommended until karma builds)")
        else:
            print(f"[Reddit] Posting via brand account to r/{subreddit}")
        # TODO: Integrate with PRAW or browser automation
        print(f"Title: {title}\nContent preview: {content[:200]}...")
        return {"status": "posted", "subreddit": subreddit}
    
    def engage_in_thread(self, post_url: str, comment: str):
        print(f"[Reddit] Engaging in thread: {post_url}")
        # TODO: Real comment posting
        return {"status": "commented"}

# Example usage
if __name__ == "__main__":
    agent = RedditAgent(post_as_user=True)
    post = agent.generate_content("managing multiple AI freelance gigs while job hunting")
    agent.post_to_reddit("jobsearch", "How I manage 5 AI gigs + job applications without losing my mind", post)