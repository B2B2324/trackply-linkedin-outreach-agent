from src.llm import call_llm
from src.prompts import load_prompt
from src.supabase_client import save_conversation

# TODO: Import or call your existing Job Coach agent from Agentic Labs
# Example interface:
# from agentic_labs.job_coach import answer_question

def call_job_coach(question: str, context: dict = None) -> str:
    """
    Handoff to the existing Trackply Job Coach (Agentic Labs powered).
    Replace this with actual import/call to your Job Coach agent.
    """
    # Placeholder - in real implementation, call your Job Coach LangGraph agent
    system = "You are the Trackply Job Coach. Answer helpfully using Trackply features and the user's context."
    user = f"Question: {question}\nContext: {context or 'No extra context'}"
    try:
        return call_llm(system, user)
    except:
        return "Thanks for the question! The Trackply Job Coach can help with that - would you like me to connect you to it or share the link?"

def conversational_node(state):
    print("[Conversational] Processing with possible Job Coach handoff...")
    system_prompt = load_prompt("conversational_prompt.txt")
    
    for target in state.get("targets", []):
        if target.get("has_new_reply"):
            reply_content = target.get("new_reply_content", "")
            
            # Decide if we should hand off to Job Coach
            if any(kw in reply_content.lower() for kw in ["feature", "how does", "trackply", "job coach", "meta agent", "gig", "application"]):
                job_coach_response = call_job_coach(reply_content, {"profile": target})
                target["generated_reply"] = job_coach_response
            else:
                # Normal outreach conversational flow
                user_prompt = f"Profile: {target}\nReply: {reply_content}"
                reply = call_llm(system_prompt, user_prompt)
                target["generated_reply"] = reply
            
            # Save conversation
            lead_id = state.get("supabase_lead_ids", {}).get(target.get("profile_url"))
            if lead_id:
                thread = [
                    {"from": "user", "content": reply_content},
                    {"from": "assistant", "content": target.get("generated_reply")}
                ]
                save_conversation(lead_id, thread)
    return state