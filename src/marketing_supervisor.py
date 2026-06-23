from langgraph.graph import StateGraph, END

# Top-level supervisor for the entire Agentic Marketing OS
# Can orchestrate LinkedIn, Reddit, SEO, and future agents

def marketing_supervisor(state):
    print("[Marketing Supervisor] Deciding which agents to run today...")
    # Example logic: run LinkedIn outreach daily, SEO 3x/week, Reddit as needed
    agents_to_run = ["linkedin_outreach"]
    if state.get("day_of_week") in [1, 3, 5]:  # Mon, Wed, Fri example
        agents_to_run.append("seo_content")
    if state.get("need_reddit_engagement"):
        agents_to_run.append("reddit")
    
    state["agents_to_run_today"] = agents_to_run
    return state

def build_marketing_graph():
    workflow = StateGraph(dict)  # Can be expanded with full shared state
    workflow.add_node("supervisor", marketing_supervisor)
    # Add edges to individual agents later
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", END)
    return workflow.compile()