from src.llm import call_llm

class RedditAgent:
    """Reddit content & engagement agent for Trackply."""

    def __init__(self, post_as_user: bool = True):
        self.post_as_user = post_as_user

    def generate_post(self, topic: str) -> str:
        system = "You are the founder of Trackply writing in an authentic voice."
        user = f"Write a natural Reddit-style post about: {topic}. End with a question to drive engagement."
        return call_llm(system, user)

    def generate_comment(self, context: str) -> str:
        system = "Respond helpfully on Reddit as the Trackply founder."
        user = f"Context: {context}\nWrite a valuable, non-salesy comment."
        return call_llm(system, user)

    def run_daily(self, topics: list[str]):
        for topic in topics:
            post = self.generate_post(topic)
            print(f"\n[Reddit] Generated post for topic: {topic}")
            print(post[:400] + "...\n")

if __name__ == "__main__":
    agent = RedditAgent(post_as_user=True)
    agent.run_daily(["managing multiple AI freelance gigs while job hunting"])