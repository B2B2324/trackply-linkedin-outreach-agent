from src.llm import call_llm

class SEOContentAgent:
    """SEO Content generation agent for trackply.com/blogs."""

    def generate_article(self, topic: str) -> str:
        system = "Write high-quality, founder-voice articles for the Trackply blog."
        user = f"Topic: {topic}\nWrite a helpful, SEO-optimized article in a natural voice."
        return call_llm(system, user)

    def run_daily(self, topics: list[str]):
        for topic in topics:
            article = self.generate_article(topic)
            print(f"\n[SEO] Generated article for: {topic}")
            print(article[:500] + "...\n")

if __name__ == "__main__":
    agent = SEOContentAgent()
    agent.run_daily(["best AI job application tracker 2026", "managing multiple AI freelance gigs"])