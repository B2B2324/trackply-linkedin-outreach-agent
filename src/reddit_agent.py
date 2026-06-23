from src.llm import call_llm
from src.prompts import load_prompt

class RedditAgent:
    def __init__(self, post_as_user: bool = True):
        self.post_as_user = post_as_user

    def generate_post(self, topic: str, style: str = "founder"):
        system = load_prompt("seo_writer_prompt.txt") or "Write as the founder of Trackply in a helpful, authentic voice."
        user = f"""Write a natural Reddit-style post about: {topic}.
Style: {style} (founder voice - personal, honest, lightly mention Trackply when it fits naturally).
Make it engaging, not salesy. Include a question at the end to drive comments."""
        return call_llm(system, user)

    def generate_comment(self, post_context: str):
        system = "You are responding helpfully on Reddit as the founder of Trackply. Be genuine and add value."
        user = f"Post context: {post_context}\nWrite a natural, helpful comment that adds value and lightly mentions Trackply if relevant."
        return call_llm(system, user)

    def post_to_subreddit(self, subreddit: str, title: str, content: str):
        mode = "as founder (you)" if self.post_as_user else "as Trackply brand"
        print(f"[Reddit] Posting to r/{subreddit} {mode}")
        print(f"Title: {title}")
        print(f"Content preview: {content[:300]}...")
        # TODO: Add PRAW or browser automation here
        return {"status": "queued_for_review", "subreddit": subreddit, "title": title}

    def engage_with_post(self, post_url: str, comment: str):
        print(f"[Reddit] Engaging with post: {post_url}")
        # TODO: Real commenting
        return {"status": "comment_queued", "comment": comment}

    def run_daily_engagement(self, topics: list):
        for topic in topics:
            post = self.generate_post(topic)
            self.post_to_subreddit("jobsearch", f"How I'm managing AI freelance + job search chaos", post)
            # Could also generate comments on relevant threads

if __name__ == "__main__":
    agent = RedditAgent(post_as_user=True)
    agent.run_daily_engagement(["managing multiple AI gigs while job hunting"])