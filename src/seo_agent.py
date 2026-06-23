from src.llm import call_llm

class SEOContentAgent:
    def run_pipeline(self, keywords: list):
        for kw in keywords:
            research = f"Key insights about {kw} in 2026"
            article = call_llm("Write a helpful founder-voice article.", f"Topic: {kw}\nResearch: {research}")
            print(f"[SEO] Generated article for: {kw}")
            # TODO: Publish to trackply.com/blogs

if __name__ == "__main__":
    SEOContentAgent().run_pipeline(["AI job application tracker"])