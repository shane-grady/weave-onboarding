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
            print(f"[RESEARCH] Got {len(tools)} tools for user {user_id}: {[t.name for t in tools]}", flush=True)
        except Exception as e:
            print(f"Failed to get tools: {e}\n{traceback.format_exc()}", flush=True)
            return {"first_name": "there", "insights": []}

        graph = self._build_graph(tools)

        state = {"messages": [HumanMessage(
            content=f"{RESEARCH_TRIGGER}. Start with GMAIL_GET_PROFILE to get the email and display name, then extract the domain from the email (the part after @). Use GMAIL_SEARCH_PEOPLE with the user's DISPLAY NAME (not the email address) as the query — this returns associated email IDs that reveal where they work. Then search for the EXACT email domain (e.g. if email is user@weave.cloud, search for \"weave.cloud\") to identify the company — never search the company name without the domain. For consumer email domains (gmail.com, yahoo.com, hotmail.com, outlook.com, etc.), use any company or organization info found from the GMAIL_SEARCH_PEOPLE results to search the web for their LinkedIn profile. Then find their LinkedIn profile. Return JSON."
        )]}

        try:
            result = await graph.ainvoke(state, {"recursion_limit": 40})
        except Exception as e:
            print(f"Graph execution error: {e}\n{traceback.format_exc()}", flush=True)
            raise

        # Log all messages in the graph execution to trace tool calls and responses
        for i, msg in enumerate(result["messages"]):
            msg_type = type(msg).__name__
            content_preview = str(msg.content)[:500] if msg.content else "(empty)"
            print(f"[RESEARCH] Message {i} ({msg_type}): {content_preview}", flush=True)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"[RESEARCH]   Tool call: {tc.get('name', '?')} args={json.dumps(tc.get('args', {}))[:300]}", flush=True)
            if hasattr(msg, 'name') and msg.name:
                print(f"[RESEARCH]   Tool response for: {msg.name}", flush=True)

        # Extract LinkedIn URLs from ToolMessage objects (EXA citations etc.)
        extracted_linkedin_urls = []
        for msg in result["messages"]:
            if type(msg).__name__ == 'ToolMessage' and msg.content:
                content = str(msg.content)
                urls = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[^\s"\'<>,\)]+', content)
                for url in urls:
                    url = url.rstrip('.')
                    if url not in extracted_linkedin_urls:
                        extracted_linkedin_urls.append(url)
        if extracted_linkedin_urls:
            print(f"[RESEARCH] Found {len(extracted_linkedin_urls)} LinkedIn URLs in ToolMessages: {extracted_linkedin_urls}", flush=True)

        raw = result["messages"][-1].content if result["messages"] else ""
        return self._parse_response(raw, extracted_linkedin_urls=extracted_linkedin_urls)

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

    def _parse_response(self, raw: str, extracted_linkedin_urls: list = None) -> dict:
        print(f"[PARSE] Raw LLM output ({len(raw)} chars):\n{raw[:2000]}", flush=True)
        if len(raw) > 2000:
            print(f"[PARSE] ... (truncated, full length: {len(raw)})", flush=True)

        parsed = None
        try:
            parsed = json.loads(raw)
            print(f"[PARSE] Direct JSON parse succeeded, top-level keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}", flush=True)
        except json.JSONDecodeError as e:
            print(f"[PARSE] Direct JSON parse failed: {e}", flush=True)
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                print(f"[PARSE] Regex matched {len(match.group())} chars", flush=True)
                try:
                    parsed = json.loads(match.group())
                    print(f"[PARSE] Regex JSON parse succeeded, top-level keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed).__name__}", flush=True)
                except json.JSONDecodeError as e2:
                    print(f"[PARSE] Regex JSON parse failed: {e2}", flush=True)
            else:
                print("[PARSE] No JSON object found by regex", flush=True)

        if not parsed or not isinstance(parsed, dict):
            print("[PARSE] No valid dict parsed, returning fallback", flush=True)
            return {"first_name": "there", "full_name": "", "insights": []}

        return self._normalize(parsed, extracted_linkedin_urls=extracted_linkedin_urls or [])

    # Patterns to classify string values by content, not by key name
    _EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    _URL_RE = re.compile(r'https?://')
    _LINKEDIN_RE = re.compile(r'linkedin\.com/', re.IGNORECASE)

    # Key substrings → insight label. Checked against the flattened key path.
    _KEY_HINTS = [
        ('first_name', None),     # special: extracted as first_name, not an insight
        ('full_name', None),      # special: extracted as full_name
        ('linkedin_url', None),   # special: extracted as linkedin_url
        ('email', 'Email'),
        ('company', 'Company'),
        ('organi', 'Company'),    # matches organization, organisation
        ('role', 'Role'),
        ('title', 'Role'),
        ('position', 'Role'),
        ('headline', 'Role'),
        ('location', 'Location'),
        ('city', 'Location'),
        ('region', 'Location'),
        ('industry', 'Industry'),
        ('sector', 'Industry'),
        ('website', 'Website'),
        ('domain', 'Website'),
        ('url', 'Website'),       # generic url fallback
        ('linkedin', 'LinkedIn'),
        ('about', 'About'),
        ('summary', 'About'),
        ('bio', 'About'),
        ('description', 'About'),
        ('overview', 'About'),
        ('interest', 'Interests'),
        ('hobby', 'Interests'),
        ('known_for', 'Known For'),
        ('notable', 'Known For'),
        ('achievement', 'Known For'),
        ('education', 'Education'),
        ('school', 'Education'),
        ('university', 'Education'),
        ('phone', 'Phone'),
        ('contact', 'Contacts'),
    ]

    def _normalize(self, data: dict, extracted_linkedin_urls: list = None) -> dict:
        """Normalize any LLM response shape into { first_name, full_name, linkedin_url, insights }."""
        print(f"[NORMALIZE] Input keys: {list(data.keys())}", flush=True)
        print(f"[NORMALIZE] Input data: {json.dumps(data, default=str)[:2000]}", flush=True)

        # Unwrap single-key wrapper (e.g. {"profile_research": {...actual data...}})
        if len(data) == 1:
            only_key = next(iter(data))
            if isinstance(data[only_key], dict):
                print(f"[NORMALIZE] Unwrapping single-key wrapper: {only_key!r}", flush=True)
                data = data[only_key]

        # Flatten the entire structure into (key_path, string_value) pairs
        flat = []
        self._flatten(data, '', flat)
        print(f"[NORMALIZE] Flattened {len(flat)} string values", flush=True)

        first_name = ''
        full_name = ''
        linkedin_url = ''
        insights = []
        seen_labels = set()

        # First pass: check for an existing well-formed insights array
        for key, val in data.items():
            if isinstance(val, list) and val and isinstance(val[0], dict) and 'label' in val[0] and 'value' in val[0]:
                for item in val:
                    if isinstance(item, dict) and item.get("label") and item.get("value"):
                        label = item["label"]
                        if label not in seen_labels:
                            insights.append({"label": label, "value": str(item["value"])})
                            seen_labels.add(label)

        # Second pass: classify each flattened value by key path and content
        for key_path, val in flat:
            kp = key_path.lower()
            val_str = str(val).strip()
            if not val_str:
                continue

            # Classify by key name hints
            matched_label = None
            for hint, label in self._KEY_HINTS:
                if hint in kp:
                    matched_label = label
                    break

            # Special fields
            if matched_label is None:
                # Fall back to content-based detection
                if self._EMAIL_RE.match(val_str):
                    matched_label = 'Email'
                elif self._LINKEDIN_RE.search(val_str):
                    matched_label = 'LinkedIn'
                elif self._URL_RE.search(val_str):
                    matched_label = 'Website'

            # Handle special extractions (not insights)
            if 'first_name' in kp and not first_name:
                first_name = val_str
                continue
            if 'full_name' in kp and not full_name:
                full_name = val_str
                continue
            if 'linkedin_url' in kp and not linkedin_url:
                linkedin_url = val_str
                print(f"[NORMALIZE] Extracted linkedin_url from key path {key_path!r}: {val_str[:100]}", flush=True)
                continue
            if matched_label is None and 'name' in kp and not first_name:
                # Only treat as a person name if the key path suggests it's about a person,
                # not a company/org/domain/product name
                is_person_key = not any(x in kp for x in ('company', 'organi', 'domain', 'product', 'brand', 'site', 'app'))
                parts = val_str.split()
                if is_person_key and 1 <= len(parts) <= 4:
                    if not full_name:
                        full_name = val_str
                    if not first_name:
                        first_name = parts[0]
                    continue
            if self._LINKEDIN_RE.search(val_str) and not linkedin_url:
                linkedin_url = val_str

            # Add as insight if we have a label
            if matched_label and matched_label not in seen_labels:
                insights.append({"label": matched_label, "value": val_str})
                seen_labels.add(matched_label)

        # Extract name and role from note/description fields (e.g. linkedin_profile.note)
        # These contain free-text like "Daniel F. — Product/UX/UI professional, potentially a Scrum Master"
        for key_path, val_str in flat:
            kp = key_path.lower()
            if 'note' not in kp and 'remark' not in kp:
                continue
            # Try to extract a name pattern like "FirstName L." or "FirstName LastName"
            if not first_name:
                name_match = re.match(r'([A-Z][a-z]+(?:\s+[A-Z]\.|\s+[A-Z][a-z]+)*)', val_str)
                if name_match:
                    extracted = name_match.group(1).strip().rstrip('.')
                    # Make sure it's not a common word / sentence start
                    if len(extracted) >= 2 and extracted.split()[0].isalpha():
                        if not full_name:
                            full_name = extracted
                        first_name = extracted.split()[0]
                        print(f"[NORMALIZE] Extracted name from note field: first_name={first_name!r}, full_name={full_name!r}", flush=True)
            # Try to extract role info after the name or from phrases like "professional", "engineer", etc.
            if 'Role' not in seen_labels:
                # Look for role-like content: text after a dash/comma, or phrases with job-related words
                role_match = re.search(r'[—–\-,]\s*(.+?)(?:\.|,\s*potentially|$)', val_str)
                if role_match:
                    role_text = role_match.group(1).strip()
                    if len(role_text) > 3:
                        insights.append({"label": "Role", "value": role_text})
                        seen_labels.add("Role")
                        print(f"[NORMALIZE] Extracted role from note field: {role_text!r}", flush=True)

        # Fallbacks
        if not first_name and full_name:
            first_name = full_name.split()[0]

        # Guard: if first_name matches a company/org insight value, it's not a person name
        company_values = {i['value'].lower() for i in insights if i['label'] in ('Company', 'Website', 'Industry')}
        if first_name and first_name.lower() in company_values:
            print(f"[NORMALIZE] Rejecting first_name={first_name!r} — matches a company insight", flush=True)
            first_name = ''
        if full_name and full_name.lower() in company_values:
            print(f"[NORMALIZE] Rejecting full_name={full_name!r} — matches a company insight", flush=True)
            full_name = ''
            if first_name and first_name.lower() in {v.split()[0].lower() for v in company_values}:
                first_name = ''

        # Use LinkedIn URLs extracted from ToolMessages if we still don't have one
        if not linkedin_url and extracted_linkedin_urls:
            # Prefer a URL whose path slug matches the user's first name or email domain
            email_val = next((i['value'] for i in insights if i['label'] == 'Email'), '')
            email_domain = email_val.split('@')[1].lower() if '@' in email_val else ''
            email_prefix = email_val.split('@')[0].lower() if '@' in email_val else ''
            candidate_name = (first_name or email_prefix).lower()

            best_url = None
            for url in extracted_linkedin_urls:
                slug = url.rstrip('/').split('/')[-1].lower().replace('-', ' ')
                if candidate_name and candidate_name in slug:
                    best_url = url
                    break
                if email_domain:
                    # Weaker signal: domain keyword in slug (e.g. "weave" in "daniel-weave")
                    domain_base = email_domain.split('.')[0]
                    if domain_base in slug:
                        best_url = url
                        break

            linkedin_url = best_url or extracted_linkedin_urls[0]
            print(f"[NORMALIZE] Using LinkedIn URL from ToolMessages: {linkedin_url}", flush=True)

        # --- Defensive validation ---

        # 1. Reject names that are status/error words, not real names
        _bad_name_words = {'no', 'not', 'none', 'multiple', 'limited', 'error', 'the', 'this',
                           'found', 'unknown', 'n/a', 'null', 'undefined', 'unavailable', 'results',
                           'email', 'contact', 'profile', 'search', 'available', 'result',
                           'domain', 'company', 'weave', 'cloud'}
        if first_name and first_name.lower() in _bad_name_words:
            print(f"[NORMALIZE] Rejecting first_name={first_name!r} — status word, not a name", flush=True)
            first_name = ''
        if full_name and full_name.split()[0].lower() in _bad_name_words:
            print(f"[NORMALIZE] Rejecting full_name={full_name!r} — starts with status word", flush=True)
            full_name = ''

        # Always fall back to email prefix for first_name
        if not first_name:
            email_val = next((i['value'] for i in insights if i['label'] == 'Email'), '')
            if '@' in email_val:
                prefix = email_val.split('@')[0]
                name_part = re.split(r'[._\-]', prefix)[0]
                if name_part.isalpha() and len(name_part) >= 2:
                    first_name = name_part.capitalize()
                    print(f"[NORMALIZE] Final fallback: first_name from email prefix: {first_name!r}", flush=True)

        # 2. LinkedIn: if a value contains linkedin.com/, it's a URL — extract to linkedin_url, not Website
        #    Also fix any LinkedIn URL that ended up in the Website insight
        validated_insights = []
        for ins in insights:
            val = ins['value']

            # LinkedIn URL in wrong field → move to linkedin_url
            if ins['label'] == 'Website' and self._LINKEDIN_RE.search(val):
                if not linkedin_url:
                    linkedin_url = val
                    print(f"[NORMALIZE] Moved LinkedIn URL from Website to linkedin_url: {val[:100]}", flush=True)
                continue  # drop from insights

            # LinkedIn insight: separate URL from status message
            if ins['label'] == 'LinkedIn':
                if self._LINKEDIN_RE.search(val):
                    if not linkedin_url:
                        linkedin_url = val
                    continue  # URL goes to linkedin_url field, not displayed as insight
                # Non-URL LinkedIn value (e.g. "not found") — keep as insight
                validated_insights.append(ins)
                continue

            # 2b. Company: verify the company matches the user's email domain
            if ins['label'] == 'Company':
                # Reject known wrong-company markers in the value itself
                company_lower = val.lower()
                _wrong_company_markers = ['communications', 'inc.', 'getweave', 'weavemfg']
                if any(marker in company_lower for marker in _wrong_company_markers):
                    print(f"[NORMALIZE] Rejecting Company={val!r} — wrong company marker", flush=True)
                    continue
                email_domain = ''
                email_val = next((i['value'] for i in insights if i['label'] == 'Email'), '')
                if '@' in email_val:
                    email_domain = email_val.split('@')[1].lower()
                if email_domain:
                    # Check all website/domain values in flattened data for a conflicting domain
                    company_domains = []
                    for kp, v in flat:
                        kpl = kp.lower()
                        if any(w in kpl for w in ('website', 'domain', 'primary_website', 'company_url')):
                            company_domains.append(v.lower().replace('https://', '').replace('http://', '').strip('/'))
                    # Also check the Website insight if already collected
                    for i in insights:
                        if i['label'] == 'Website':
                            company_domains.append(i['value'].lower().replace('https://', '').replace('http://', '').strip('/'))
                    # If we found company domain(s) and none match the email domain, discard
                    if company_domains and not any(email_domain in d for d in company_domains):
                        print(f"[NORMALIZE] Rejecting Company={val!r} — company domains {company_domains} don't match email domain {email_domain!r}", flush=True)
                        continue
                validated_insights.append(ins)
                continue

            # 3. Contacts: reject raw numeric values (history IDs leaking through)
            if ins['label'] == 'Contacts':
                if val.isdigit():
                    print(f"[NORMALIZE] Rejecting Contacts={val!r} — raw numeric ID", flush=True)
                    continue
                validated_insights.append(ins)
                continue

            # 4. Role: discard if it's clearly from the wrong company or is a sentence fragment
            if ins['label'] == 'Role':
                role_lower = val.lower()
                _wrong_company_terms = ['healthcare', 'patient engagement', 'manufacturing',
                                        'factory', 'textile', 'hospital', 'pharma', 'biotech']
                _junk_role_phrases = ['require', 'additional', 'lookup', 'details',
                                      'could not', 'not found', 'not available']
                if any(term in role_lower for term in _wrong_company_terms):
                    print(f"[NORMALIZE] Rejecting Role={val!r} — wrong company terms", flush=True)
                    continue
                if any(phrase in role_lower for phrase in _junk_role_phrases):
                    print(f"[NORMALIZE] Rejecting Role={val!r} — junk sentence fragment", flush=True)
                    continue
                if val[0:1].isalpha() and val[0] == val[0].lower():
                    print(f"[NORMALIZE] Rejecting Role={val!r} — starts with lowercase", flush=True)
                    continue

            # 5. Industry: reject wrong-company terms
            if ins['label'] == 'Industry':
                val_lower = val.lower()
                _wrong_company_terms = ['healthcare', 'patient engagement', 'manufacturing',
                                        'factory', 'textile', 'hospital', 'pharma', 'biotech']
                if any(term in val_lower for term in _wrong_company_terms):
                    print(f"[NORMALIZE] Rejecting Industry={val!r} — wrong company terms", flush=True)
                    continue

            # 6. About: reject wrong-company terms and internal metadata phrases
            if ins['label'] == 'About':
                val_lower = val.lower()
                _wrong_company_terms = ['healthcare', 'patient engagement', 'manufacturing',
                                        'factory', 'textile', 'hospital', 'pharma', 'biotech']
                _metadata_phrases = ['high for', 'low for', 'confidence', 'score']
                if any(term in val_lower for term in _wrong_company_terms):
                    print(f"[NORMALIZE] Rejecting About={val!r} — wrong company terms", flush=True)
                    continue
                if any(phrase in val_lower for phrase in _metadata_phrases):
                    print(f"[NORMALIZE] Rejecting About={val!r} — internal metadata phrase", flush=True)
                    continue
                if len(val.split()) <= 1 or len(val) < 10:
                    print(f"[NORMALIZE] Rejecting About={val!r} — too short (junk status value)", flush=True)
                    continue

            # 7. Website: should be a domain, not a linkedin URL, and must match email domain
            if ins['label'] == 'Website':
                if self._LINKEDIN_RE.search(val):
                    continue  # already handled
                # Verify website matches email domain
                email_val = next((i['value'] for i in insights if i['label'] == 'Email'), '')
                if '@' in email_val:
                    email_domain = email_val.split('@')[1].lower()
                    clean_val = val.lower().replace('https://', '').replace('http://', '').strip('/')
                    if email_domain not in clean_val:
                        print(f"[NORMALIZE] Rejecting Website={val!r} — doesn't match email domain {email_domain!r}", flush=True)
                        continue

            validated_insights.append(ins)

        insights = validated_insights

        # Ensure linkedin_url is added as a LinkedIn insight for display if we have one
        if linkedin_url and 'LinkedIn' not in {i['label'] for i in insights}:
            insights.append({"label": "LinkedIn", "value": linkedin_url})

        result = {
            "first_name": first_name or "there",
            "full_name": full_name,
            "linkedin_url": linkedin_url,
            "insights": insights,
        }
        print(f"[NORMALIZE] Output: first_name={result['first_name']!r}, full_name={result['full_name']!r}, insights_count={len(insights)}", flush=True)
        for ins in insights:
            print(f"[NORMALIZE]   {ins['label']}: {ins['value'][:100]}", flush=True)
        return result

    def _flatten(self, obj, prefix: str, out: list):
        """Recursively flatten a nested dict/list into (key_path, string_value) pairs."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._flatten(v, f"{prefix}.{k}" if prefix else k, out)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict) and 'label' in item and 'value' in item:
                    # Skip well-formed insight objects — handled separately
                    continue
                self._flatten(item, f"{prefix}[{i}]", out)
        elif isinstance(obj, str) and obj.strip():
            out.append((prefix, obj.strip()))
