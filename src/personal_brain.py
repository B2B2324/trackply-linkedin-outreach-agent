from src.llm import call_llm

# Initial Personal Brain / AI Companion foundation

class PersonalBrain:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = []  # Will connect to Supabase long-term

    def add_memory(self, content: str, source: str = "user"):
        self.memory.append({"content": content, "source": source})
        print(f"[Personal Brain] Added memory for {self.user_id}")

    def recall(self, query: str):
        system = "You are the user's Personal Brain. Answer based on their stored memories."
        user = f"Query: {query}\nMemories: {self.memory}"
        return call_llm(system, user)

    def set_reminder(self, task: str, time: str):
        print(f"[Personal Brain] Reminder set: {task} at {time}")
        # TODO: Integrate with scheduler / notifications

    def handle_input(self, input_type: str, content: str):
        if input_type == "text":
            self.add_memory(content)
        elif input_type == "voice":
            # TODO: Transcribe + add
            self.add_memory(f"[Voice note] {content}")

# Example usage
if __name__ == "__main__":
    brain = PersonalBrain("stephen")
    brain.add_memory("Wife is pregnant, due in a few months")
    brain.set_reminder("Doctor appointment", "Thursday 3pm")
    print(brain.recall("What do I have going on this week?"))