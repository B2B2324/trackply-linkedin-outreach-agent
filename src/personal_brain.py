from src.llm import call_llm

class PersonalBrain:
    """Initial Personal Brain / AI Companion."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = []

    def add_memory(self, content: str, source: str = "user"):
        self.memory.append({"content": content, "source": source})
        print(f"[Personal Brain] Memory added for {self.user_id}")

    def recall(self, query: str):
        system = "You are the user's Personal Brain. Answer helpfully based on stored memories."
        user = f"Query: {query}\nMemories: {self.memory}"
        return call_llm(system, user)

    def set_reminder(self, task: str, time: str):
        print(f"[Personal Brain] Reminder set: {task} at {time}")
        # TODO: Connect to real notification system

    def handle_text_input(self, text: str):
        self.add_memory(text)
        return "Got it. I've noted that down."

    def handle_voice_input(self, transcription: str):
        self.add_memory(f"[Voice] {transcription}")
        return "I've saved your voice note."