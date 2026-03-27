import json
import re
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

from .constants import composio, llm


RESEARCH_PROMPT = """You build a warm first impression for Weave Fabric. Research the user and return what you find.

## Steps
1. GMAIL_GET_PROFILE → get email + display name (this is the identity anchor)
2. Extract the email domain (e.g. "acme.com" from "jane@acme.com"). This domain is your PRIMARY anchor for identifying the user's company.
3. GMAIL_SEARCH_PEOPLE with that name → look for their contact card (ignore results about different people)
4. COMPOSIO_SEARCH_SEARCH: "name" + email → find LinkedIn, company, web presence
5. COMPOSIO_SEARCH_SEARCH: search for the email domain directly (e.g. "acme.com") → find the company's own website and description
6. COMPOSIO_SEARCH_SEARCH: "name" + company (if confirmed) → deeper details

## Rules
- Gmail profile is the source of truth. Discard web results about different people.
- Never include: street addresses, financial info, medical/legal info, minors, passwords.
- Frame warmly: "You're running a studio in Austin" not "CEO of janesmith.com"
- Omit anything you can't confirm.

## Company Identification (CRITICAL)
- The user's email domain is the definitive anchor for identifying their company. For example, if the user's email is "jane@weave.cloud", their company website is weave.cloud.
- ONLY use company descriptions sourced from the company's own domain (the email domain). For example, if the domain is "weave.cloud", only trust descriptions found on or explicitly about weave.cloud.
- Many company names are shared across industries. Companies like "Weave", "Spark", "Atlas", etc. can refer to dozens of unrelated businesses. NEVER assume which one the user belongs to based on the name alone — always verify using the email domain.
- If a search result describes a company with a similar name but a DIFFERENT domain or website, discard it entirely. Do not merge, blend, or mix descriptions from different companies.
- If you cannot find a description specifically from the email domain's website, use just the company name without a description rather than risking a wrong one.

## Role Verification
- Cross-check the person's role against their LinkedIn or other profile. Do not infer a role from a company description — the person's actual title/role must appear in a source tied to them.

## Output
Return ONLY JSON:
{"first_name":"...","full_name":"...","insights":[{"label":"...","value":"..."}]}

Labels to use when evidence exists: Email, Company, Role, Location, About, LinkedIn, Website, Interests, Known For. Omit labels without evidence. "first_name" is required."""


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
            print(f"Failed to get tools: {e}")
            return {"first_name": "there", "insights": []}

        graph = self._build_graph(tools)

        state = {"messages": [HumanMessage(
            content=f"{RESEARCH_TRIGGER}. Start with GMAIL_GET_PROFILE, then GMAIL_SEARCH_PEOPLE, then web search. Return JSON."
        )]}

        result = await graph.ainvoke(state, {"recursion_limit": 40})

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
