from src.llm import call_llm

class SEOContentAgent:
    def __init__(self):
        pass

    def research_topic(self, keyword: str):
        # TODO: Integrate real web search / X search here
        print(f"[SEO Agent] Researching trends for: {keyword}")
        return f"Key 2026 pain points for job seekers around {keyword}: ghost jobs, ATS, managing multiple platforms, AI freelance stacking."

    def write_article(self, topic: str, research: str):
        system = load_prompt("seo_writer_prompt.txt") or "Write helpful founder-voice content for Trackply blog."
        user = f"""Topic: {topic}
Research: {research}
Write a high-quality, SEO-optimized article (1000-1800 words) in founder voice.
Structure with headings, make it useful, and naturally mention Trackply features where relevant."""
        return call_llm(system, user)

    def generate_meta(self, title: str, content: str):
        system = "Create SEO meta title and description."
        user = f"Title: {title}\nContent summary: {content[:500]}"
        return call_llm(system, user)

    def publish_to_blog(self, title: str, content: str, meta: dict = None):
        print(f"[SEO] Ready to publish: {title}")
        # TODO: Push to trackply.com/blogs via CMS/Supabase/Vercel
        return {
            "status": "ready_to_publish",
            "title": title,
            "url": f"https://trackply.com/blogs/{title.lower().replace(' ', '-')}"
        }

    def run_content_pipeline(self, keywords: list):
        results = []
        for kw in keywords:
            research = self.research_topic(kw)
            article = self.write_article(kw, research)
            meta = self.generate_meta(kw, article)
            publish_info = self.publish_to_blog(kw, article, meta)
            results.append(publish_info)
        return results

if __name__ == "__main__":
    agent = SEOContentAgent()
    agent.run_content_pipeline(["best AI job application tracker 2026", "how to manage multiple AI freelance gigs"])