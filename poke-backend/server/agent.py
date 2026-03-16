import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

from .constants import composio, llm


RESEARCH_PROMPT = """You are building a first impression for Weave — an AI that shows users how much the internet already knows about them. The reveal should feel magical and a little unsettling, like a friend who somehow knows everything. NOT like a surveillance report or a data dump.

## Research Strategy (3 Phases, execute ALL in order)

### Phase 1: Identity (Gmail Profile — THIS IS YOUR ANCHOR)
1. GMAIL_GET_PROFILE → get the user's email address AND display name. The display name from the profile IS the user's real name. This is your **authoritative identity anchor** — all subsequent research MUST be about THIS specific person.
2. GMAIL_SEARCH_PEOPLE with the EXACT display name from step 1 → look for their OWN contact card with professional details, phone, etc. IMPORTANT: This searches the user's contacts directory. If the results return info about a DIFFERENT person (different name, different email domain), IGNORE those results — they are contacts, not the user.
3. GMAIL_GET_CONTACTS (pageSize=10) → names of frequent contacts (these are OTHER people the user talks to, NOT the user themselves)

### Phase 2: Targeted Web Research (do ALL of these)
CRITICAL: Every search MUST use the exact name + email from Phase 1. If web results describe a different person (different email, different company than what the Gmail profile suggests), DISCARD those results entirely.

4. COMPOSIO_SEARCH_SEARCH: "full name from Gmail profile" + email address from Gmail profile
5. COMPOSIO_SEARCH_SEARCH: "full name" + company name (ONLY if company was confirmed from the user's own profile/email domain, not from a contact)
6. COMPOSIO_SEARCH_SEARCH: "full name" + city (if found and confirmed to be about THIS user)
7. COMPOSIO_SEARCH_SEARCH: email address in quotes (find where it's been exposed)
8. COMPOSIO_SEARCH_NEWS: full name from Gmail profile (press mentions, articles)
9. COMPOSIO_SEARCH_EXA_ANSWER: "What is known about [full name from Gmail] who uses [email from Gmail]?"

### Phase 3: Go Deeper
10. If you find a personal website, portfolio, or interesting profile URL → COMPOSIO_SEARCH_FETCH_URL_CONTENT to extract details
11. Search for: "site:twitter.com OR site:github.com OR site:medium.com [name from Gmail profile]"
12. Search for their company + role for press mentions or staff bios
13. Search for side projects, publications, speaking engagements, board memberships

## IDENTITY VERIFICATION — CRITICAL
- The Gmail profile (email + display name) is the SINGLE SOURCE OF TRUTH for who this person is.
- GMAIL_SEARCH_PEOPLE returns the user's CONTACTS (other people), not the user's own info. Do NOT confuse a contact's details with the user's identity.
- Before using ANY fact from web research, verify it plausibly relates to the person with the Gmail profile email. If a web result is about someone with a different email, different company, or a clearly different person — DISCARD it.
- When in doubt, OMIT the insight rather than attribute someone else's information to this user.

## Cross-Referencing Rule
Before including any fact, you should ideally have found it in 2+ sources OR it comes directly from their Gmail profile (which is authoritative). Don't state facts you're uncertain about. If web results conflict with the Gmail profile identity, trust the Gmail profile.

## HARD FILTERS — NEVER include these:
- Full street addresses (city/neighborhood level ONLY)
- Property values, mortgage details, or real estate records
- Financial account numbers, salary, pricing, or revenue
- Medical, legal, or romantic information
- Names or details of minors (anyone under 18)
- Password resets, verification codes, or security tokens
- Anything that reads like a background check or public records scrape
- Information about a DIFFERENT person who happens to share a similar name

## Tone & Framing Rules
- Frame each insight like a perceptive friend's observation, not a database entry
- "You're running a design studio out of Austin" NOT "CEO of janesmith.com — design studio specializing in branding"
- "You've been creating things since before college" NOT "Started first business at age 16 selling art prints"
- "You and Mike seem close — family?" NOT "Mike Johnson (mikej@gmail.com)"
- Surprising specificity is good. Clinical data extraction is bad.
- The goal is to make them think "how did it know that?" not "I feel violated"

## Output Format
Aim for 10-16 insights. Return ONLY this JSON — no text before or after.
{
  "first_name": "their first name",
  "full_name": "their full name",
  "insights": [
    {"label": "Email", "value": "primary email (and alternate if found)"},
    {"label": "Company", "value": "what they do, framed conversationally"},
    {"label": "Role", "value": "their title or how they describe themselves"},
    {"label": "Location", "value": "city, state — no street addresses"},
    {"label": "Industry", "value": "their field, framed specifically"},
    {"label": "Education", "value": "school name"},
    {"label": "LinkedIn", "value": "profile url"},
    {"label": "Website", "value": "personal site if found"},
    {"label": "About", "value": "a warm, specific one-sentence summary of who they are"},
    {"label": "Contacts", "value": "first names only of close contacts, framed warmly"},
    {"label": "Uses", "value": "platforms they have profiles on (GitHub, Webflow, etc.)"},
    {"label": "Interests", "value": "hobbies, causes, or passions — framed as observations"},
    {"label": "Known For", "value": "achievements, press mentions, or notable projects"},
    {"label": "Side Projects", "value": "anything beyond their main job"},
    {"label": "Network", "value": "professional connections or communities they're part of"},
    {"label": "Travels To", "value": "places associated with them"}
  ]
}

Only include insights with real evidence. Omit any you cannot confirm.
"first_name" is REQUIRED. Return ONLY the JSON object."""


class ResearchAgent:
    def __init__(self):
        self.llm = llm

    async def research(self, user_id: str) -> dict:
        try:
            from .tools import get_google_tools
            tools = get_google_tools(composio, user_id)
        except Exception as e:
            print(f"Failed to get tools: {e}")
            return {"first_name": "there", "insights": []}

        model_with_tools = self.llm.bind_tools(tools)
        tool_node = ToolNode(tools)

        def call_model(state):
            system = SystemMessage(content=RESEARCH_PROMPT)
            messages = [system] + state["messages"]
            return {"messages": [model_with_tools.invoke(messages)]}

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")

        graph = workflow.compile()

        state = {"messages": [HumanMessage(
            content="Research this user's digital footprint now. Start with GMAIL_GET_PROFILE, then search their contacts, then do thorough web research. Find specific, surprising things about them — the kind of details that make someone say 'how did you know that?' Aim for 10-16 insights."
        )]}

        result = await graph.ainvoke(state, {"recursion_limit": 40})

        raw = result["messages"][-1].content if result["messages"] else ""
        return self._parse_response(raw)

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
