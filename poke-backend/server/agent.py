import json
import re
import traceback
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

from .constants import composio, llm


RESEARCH_PROMPT = """You build a warm first impression for Weave Fabric. Research the user and return what you find.

## Steps
1. GMAIL_GET_PROFILE → get email + display name (this is the identity anchor)
2. Extract the email domain (e.g. "acme.com" from "jane@acme.com"). This domain is your PRIMARY anchor for identifying the user's company.
3. GMAIL_SEARCH_PEOPLE with that name → look for their contact card (ignore results about different people)
4. COMPOSIO_SEARCH_WEB: "name" + email → find LinkedIn, company, web presence
5. COMPOSIO_SEARCH_WEB: search for the EXACT email domain (e.g. "weave.cloud", not just "weave") → find the company's own website and description
6. COMPOSIO_SEARCH_WEB: "name" + "LinkedIn" + company or email domain → find their specific LinkedIn profile
7. COMPOSIO_SEARCH_FETCH_URL_CONTENT: fetch the LinkedIn profile URL from step 6 → extract current role, headline, company, connection count, and any other public details
8. COMPOSIO_SEARCH_WEB: "name" + company (if confirmed) → deeper details

## LinkedIn Identification (CRITICAL)
- When multiple LinkedIn profiles appear for the same name, pick the one that:
  a) Has a company or role matching the email domain (e.g. if email is daniel@weave.cloud, pick the LinkedIn that shows Weave)
  b) Has the most connections/followers (indicates the real, active profile)
  c) Has recent activity
- Always use COMPOSIO_SEARCH_FETCH_URL_CONTENT to read the actual LinkedIn page — do not rely solely on search snippets.
- Include the LinkedIn profile URL in the output as the "LinkedIn" label value.

## Rules
- Gmail profile is the source of truth. Discard web results about different people.
- Never include: street addresses, financial info, medical/legal info, minors, passwords.
- Frame warmly: "You're running a studio in Austin" not "CEO of janesmith.com"
- When in doubt between two verified options, pick the best match. Only omit a field if there is genuinely no data available for it.
- If two sources contradict each other, prefer the source that matches the user's email domain.

## Company Identification (CRITICAL)
- The user's company website is EXACTLY their email domain. If the user's email is user@weave.cloud, their company website is weave.cloud — not weavemfg.com, not weavecloud.com, not any other domain. ONLY use information from the exact email domain. Any search result from a different domain is about a DIFFERENT company and must be completely ignored.
- When web search returns multiple companies with similar names, only use the one whose domain matches the user's email.
- Discard company descriptions from any organization whose domain does not match.
- If you cannot find a description specifically from the email domain's website, use just the company name without a description rather than risking a wrong one.

## Role Extraction
- Prefer the LinkedIn Experience section: it lists positions grouped by company with title and dates.
- When a user has multiple roles at the same company, use the FIRST listed role under that company (LinkedIn's display order reflects the user's own prioritization).
- If the Experience section is not available or unreadable, fall back to the LinkedIn headline (the line directly under the user's name).
- Do not infer a role from a company description — it must come from a source tied to the person.

## About / Known For
- Summarize the user's LinkedIn About section in 1-2 complete sentences that capture their core focus and strengths.
- Paraphrase naturally — do not copy verbatim, but preserve the meaning.
- The About field must be a clean, complete thought — never truncate mid-sentence.
- If the About section is not available, use other profile details (headline, experience descriptions) to write a brief summary.

## Output
Your goal is to populate as many of the following fields as possible. Actively try to find data for each one — only omit a field if you genuinely found nothing for it.

Return ONLY JSON:
{"first_name":"...","full_name":"...","linkedin_url":"...","insights":[{"label":"...","value":"..."}]}

Expected insight labels (include all that have data):
- Email: the user's email address
- Company: company name, from the email domain
- Role: current job title (from LinkedIn Experience, or headline as fallback)
- Location: city/region if found on LinkedIn or other profile
- About: 1-2 sentence summary of who they are and what they do
- LinkedIn: the full LinkedIn profile URL
- Website: company or personal website
- Interests: professional interests if evident from their profile
- Known For: notable work, projects, or public presence

"first_name" is required. "linkedin_url" should be the full LinkedIn profile URL if found (omit if not found)."""


CONVERSATION_PROMPT = """You are Fabric, the voice of Weave Fabric. You already know enough about this person to speak naturally and directly.

## Personality
- Confident and direct. Warm but not eager.
- Talk like a real person — casual, concise, no corporate polish.
- A little playful. Dry humor is fine. Never forced.
- You respect who you're talking to. Let that come through naturally.

## Using what you know
- Reference relevant details naturally in conversation.
- Don't list facts, don't summarize research, don't explain where anything came from.
- If a detail is uncertain or missing, leave it out.

## What you know about this person
{research_json}

## Constraints
- 1-3 sentences unless they ask for more.
- No emoji. No exclamation marks. No filler.
- Never mention tools, APIs, Gmail, or any technical process.
- Never include street addresses, financial info, medical/legal info, or passwords.
- Match their energy. If they're brief, be brief. If they're more open, you can open up too."""


RESEARCH_TRIGGER = "SYSTEM: Perform initial research"


class WeaveAgent:
    def __init__(self):
        self.llm = llm

    def _build_graph(self, tools, research_context: dict = None):
        model_with_tools = self.llm.bind_tools(tools)
        tool_node = ToolNode(tools)

        def call_model(state):
            current_message = state["messages"][-1].content
            is_research = RESEARCH_TRIGGER in current_message

            if is_research:
                system_content = RESEARCH_PROMPT
            else:
                system_content = CONVERSATION_PROMPT.format(
                    research_json=json.dumps(research_context or {}, indent=2)
                )

            system = SystemMessage(content=system_content)
            messages = [system] + state["messages"]
            return {"messages": [model_with_tools.invoke(messages)]}

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")

        return workflow.compile()

    async def research(self, user_id: str) -> dict:
        try:
            from .tools import get_google_tools
            tools = get_google_tools(composio, user_id)
        except Exception as e:
            print(f"Failed to get tools: {e}\n{traceback.format_exc()}", flush=True)
            return {"first_name": "there", "insights": []}

        graph = self._build_graph(tools)

        state = {"messages": [HumanMessage(
            content=f"{RESEARCH_TRIGGER}. Start with GMAIL_GET_PROFILE, then GMAIL_SEARCH_PEOPLE, then web search. Return JSON."
        )]}

        try:
            result = await graph.ainvoke(state, {"recursion_limit": 40})
        except Exception as e:
            print(f"Graph execution error: {e}\n{traceback.format_exc()}", flush=True)
            raise

        raw = result["messages"][-1].content if result["messages"] else ""
        return self._parse_response(raw)

    async def chat(self, user_id: str, message: str, research_context: dict, history: list = None) -> str:
        try:
            from .tools import get_google_tools
            tools = get_google_tools(composio, user_id)
        except Exception as e:
            print(f"Failed to get tools: {e}")
            tools = []

        graph = self._build_graph(tools, research_context=research_context)

        messages = []
        for entry in (history or []):
            messages.append(HumanMessage(content=entry["content"]))
            if entry.get("response"):
                messages.append(AIMessage(content=entry["response"]))
        messages.append(HumanMessage(content=message))

        state = {"messages": messages}
        result = await graph.ainvoke(state, {"recursion_limit": 10})

        return result["messages"][-1].content if result["messages"] else ""

    async def generate_opening(self, research_data: dict) -> str:
        prompt = CONVERSATION_PROMPT.format(
            research_json=json.dumps(research_data, indent=2)
        )
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(
                content="Generate your opening line to this person. You just finished learning about them. Make it personal, short, and conversational. 1-2 sentences max."
            ),
        ]
        response = await self.llm.ainvoke(messages)
        return response.content

    def _parse_response(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {"first_name": "there", "full_name": "", "insights": []}
