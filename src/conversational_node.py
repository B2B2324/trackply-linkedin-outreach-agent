from src.llm import call_llm
from src.prompts import load_prompt
from src.supabase_client import save_conversation

# Job Coach handoff (Agentic Labs)
def call_job_coach(question: str, context: dict = None) -> str:
    """
    Calls the existing Trackply Job Coach (powered by Agentic Labs).
    Replace with actual import from your Job Coach module when ready.
    """
    system = """You are Kemba, the Trackply Job Coach. 
You are helpful, direct, and speak in a natural founder-like tone when appropriate.
Use real Trackply features (Meta Agent, gig tracker, scam detector, targeted applications) in your answers.
Keep responses concise and actionable."""
    user = f"Question from LinkedIn lead: {question}\nLead context: {context or 'New lead from outreach'}\nAnswer helpfully and naturally."
    try:
        return call_llm(system, user)
    except Exception as e:
        return f"Great question! The Trackply Job Coach (Kemba) can give you a detailed answer on that. Want me to share the link or walk you through it?"

def conversational_node(state):
    print("[Conversational] Running with natural voice + Job Coach handoff...")
    system_prompt = load_prompt("conversational_prompt.txt")

    for target in state.get("targets", []):
        if target.get("has_new_reply"):
            reply_content = target.get("new_reply_content", "")

            # Smart handoff to Job Coach for Trackply-related questions
            job_keywords = ["trackply", "meta agent", "gig tracker", "application", "job coach", "how do i", "feature"]
            if any(kw in reply_content.lower() for kw in job_keywords):
                response = call_job_coach(reply_content, {"profile": target})
            else:
                user_prompt = f"Profile: {target}\nReply from lead: {reply_content}\nRespond naturally as the founder of Trackply."
                response = call_llm(system_prompt, user_prompt)

            target["generated_reply"] = response

            lead_id = state.get("supabase_lead_ids", {}).get(target.get("profile_url"))
            if lead_id:
                thread = [
                    {"from": "user", "content": reply_content},
                    {"from": "assistant", "content": response}
                ]
                save_conversation(lead_id, thread)

    return state