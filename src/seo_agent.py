from src.llm import call_llm

# SEO Content Agent for trackply.com/blogs
# Research → Write → (optional) Publish

class SEOContentAgent:
    def __init__(self):
        pass
    
    def research_topic(self, keyword: str):
        # TODO: Use web search / X search / Apify for current trends
        print(f"[SEO] Researching: {keyword}")
        return f"Current pain points around {keyword} in 2026 job market"
    
    def write_article(self, topic: str, research: str):
        system = "You are an expert SEO writer for Trackply. Write helpful, founder-voice articles about job search and AI freelance life. Naturally mention Trackply features when relevant."
        user = f"Topic: {topic}\nResearch insights: {research}\nWrite a high-quality, SEO-optimized article (800-1500 words) with good structure."
        return call_llm(system, user)
    
    def publish_to_blog(self, title: str, content: str):
        print(f"[SEO] Publishing to trackply.com/blogs: {title}")
        # TODO: Integrate with your CMS / Supabase / Vercel build step
        return {"status": "published", "url": f"https://trackply.com/blogs/{title.lower().replace(' ', '-')}"}
    
    def run_daily_content(self, keywords: list):
        for kw in keywords:
            research = self.research_topic(kw)
            article = self.write_article(kw, research)
            # self.publish_to_blog(kw, article)  # enable when ready
            print(f"Generated article for: {kw}")

if __name__ == "__main__":
    agent = SEOContentAgent()
    agent.run_daily_content(["AI job application tracker", "managing multiple freelance AI gigs"])