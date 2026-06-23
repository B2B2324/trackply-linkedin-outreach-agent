from src.llm import call_llm

class RedditAgent:
    def __init__(self, post_as_user=True):
        self.post_as_user = post_as_user

    def generate_post(self, topic: str):
        system = "Write as the founder of Trackply in an authentic, helpful voice."
        user = f"Write a natural Reddit post about: {topic}. End with a question."
        return call_llm(system, user)

    def generate_comment(self, context: str):
        system = "Respond helpfully on Reddit as the Trackply founder."
        user = f"Context: {context}\nWrite a valuable comment."
        return call_llm(system, user)

    def run_engagement(self, topics: list):
        for topic in topics:
            post = self.generate_post(topic)
            print(f"[Reddit] Generated post for r/jobsearch: {post[:150]}...")
            # TODO: Actual posting logic

if __name__ == "__main__":
    RedditAgent().run_engagement(["managing AI gigs + job search"])