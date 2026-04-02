from composio import Composio


REQUESTED_TOOLS = [
    "GMAIL_GET_PROFILE",
    "GMAIL_SEARCH_PEOPLE",
    "GMAIL_GET_CONTACTS",
    "COMPOSIO_SEARCH_WEB",
    "COMPOSIO_SEARCH_NEWS",
    "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
    "COMPOSIO_SEARCH_EXA_ANSWER",
]


def get_stripe_tools(composio_client: Composio, user_id: str):
    return composio_client.tools.get(user_id, toolkits=["STRIPE"])


def get_google_tools(composio_client: Composio, user_id: str):
    print(f"[TOOLS] Requesting {len(REQUESTED_TOOLS)} tools for user {user_id}: {REQUESTED_TOOLS}", flush=True)

    try:
        tools = composio_client.tools.get(
            user_id,
            tools=REQUESTED_TOOLS,
        )
    except Exception as e:
        print(f"[TOOLS] ERROR from Composio SDK: {type(e).__name__}: {e}", flush=True)
        raise

    returned_names = []
    for t in tools:
        name = getattr(t, 'name', None) or getattr(t, 'function', {}).get('name', '?')
        returned_names.append(name)

    print(f"[TOOLS] Composio returned {len(tools)} tools: {returned_names}", flush=True)

    missing = set(REQUESTED_TOOLS) - set(returned_names)
    if missing:
        print(f"[TOOLS] WARNING — requested but NOT returned: {sorted(missing)}", flush=True)

    extra = set(returned_names) - set(REQUESTED_TOOLS)
    if extra:
        print(f"[TOOLS] NOTE — returned but not requested: {sorted(extra)}", flush=True)

    # Log each tool's details
    for t in tools:
        name = getattr(t, 'name', None) or getattr(t, 'function', {}).get('name', '?')
        desc = getattr(t, 'description', None) or getattr(t, 'function', {}).get('description', '')
        print(f"[TOOLS]   {name}: {str(desc)[:120]}", flush=True)

    return tools
