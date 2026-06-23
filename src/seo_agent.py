import time
import random
from src.llm import call_llm

class SEOContentAgent:
    """SEO agent that writes 1-2 high-quality blog posts per day for trackply.com/blogs."""

    def generate_blog_post(self, topic: str):
        system = """You are Stephen, founder of Trackply. Write helpful, founder-voice articles about job search and AI freelance life.
        Focus on real problems and how Trackply helps, without being overly promotional."""
        user = f"Write a high-quality SEO article about: {topic}"
        return call_llm(system, user)

    def run_daily(self, num_posts: int = 2):
        topics = [
            "Why most job trackers fail at helping you actually land jobs in 2026",
            "How AI freelancers are managing multiple gigs without losing their minds",
            "The hidden cost of applying to 100+ jobs every month"
        ]
        
        for i in range(min(num_posts, len(topics))):
            post = self.generate_blog_post(topics[i])
            print(f"\n[SEO] Generated blog post #{i+1}:")
            print(post[:600] + "...\n")
            time.sleep(random.randint(30, 90))

if __name__ == "__main__":
    agent = SEOContentAgent()
    agent.run_daily(num_posts=2)