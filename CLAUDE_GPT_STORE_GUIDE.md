# How to Get Trackply Listed in Claude Connections & ChatGPT Store

## 1. Build Proper Tool Definitions (MCP Tools)
We are already doing this in the `mcp_tools/` folder.

Key tools to expose:
- add_job_to_tracker
- get_pipeline_summary
- check_scam_ghost_detector
- update_application_status
- get_kemba_advice

## 2. Create Clear, Compelling Descriptions
Each tool needs a good description so LLMs understand when to use it.

## 3. Authentication
Users must connect their Trackply account (OAuth or API key) before tools can be used.

## 4. For Claude (Anthropic)
- Use Anthropic's tool use format
- Can be exposed via Custom Projects or through platforms that support Anthropic tool calling
- Good descriptions + reliable tools = higher chance of being recommended by Claude

## 5. For ChatGPT / OpenAI
- Use GPT Actions or create a Custom GPT
- Define functions clearly
- Submit to the GPT Store if you want public discovery

## 6. Marketing & Positioning
- Create a clear value proposition: "Sync your Trackply account with Claude or ChatGPT so your job search stays organized."
- Make it easy for users to connect their account

## Cross-Compatibility with Grok
Claude and Grok are partially cross-compatible.
- If you build tools using LangChain/LangGraph with standard function calling, they often work on both with minor adjustments.
- Claude uses its own tool format, while Grok supports OpenAI-compatible function calling in many cases.
- Best practice: Build once with LangChain, then adapt the tool schema for each platform if needed.