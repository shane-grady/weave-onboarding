from composio import Composio


GMAIL_TOOLS = [
    "GMAIL_GET_PROFILE",
    "GMAIL_SEARCH_PEOPLE",
    "GMAIL_GET_CONTACTS",
]

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
    # Fetch Gmail tools by name
    print(f"[TOOLS] Requesting {len(GMAIL_TOOLS)} Gmail tools for user {user_id}: {GMAIL_TOOLS}", flush=True)
    try:
        gmail_tools = composio_client.tools.get(
            user_id,
            tools=GMAIL_TOOLS,
        )
    except Exception as e:
        print(f"[TOOLS] ERROR fetching Gmail tools: {type(e).__name__}: {e}", flush=True)
        raise
    print(f"[TOOLS] Gmail call returned {len(gmail_tools)} tool(s)", flush=True)

    # Fetch search tools via toolkit
    print(f"[TOOLS] Requesting composio_search toolkit for user {user_id}", flush=True)
    try:
        search_tools = composio_client.tools.get(
            user_id,
            toolkits=["composio_search"],
        )
    except Exception as e:
        print(f"[TOOLS] ERROR fetching composio_search toolkit: {type(e).__name__}: {e}", flush=True)
        raise
    print(f"[TOOLS] composio_search toolkit returned {len(search_tools)} tool(s)", flush=True)

    # Combine
    tools = gmail_tools + search_tools
    print(f"[TOOLS] Combined total: {len(tools)} tools", flush=True)

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


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    client = Composio(api_key=os.environ.get("COMPOSIO_API_KEY"))
    test_user_id = "test-user-debug"

    # (1) Single tool, no user_id
    print("=" * 60)
    print("TEST 1: tools.get(tools=['COMPOSIO_SEARCH_WEB']) — no user_id")
    print("=" * 60)
    try:
        result = client.tools.get(tools=["COMPOSIO_SEARCH_WEB"])
        print(f"  Returned {len(result)} tool(s)")
        for t in result:
            name = getattr(t, "name", None) or getattr(t, "function", {}).get("name", "?")
            print(f"    -> {name}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # (2) Single tool, with user_id
    print()
    print("=" * 60)
    print(f"TEST 2: tools.get(user_id='{test_user_id}', tools=['COMPOSIO_SEARCH_WEB'])")
    print("=" * 60)
    try:
        result = client.tools.get(test_user_id, tools=["COMPOSIO_SEARCH_WEB"])
        print(f"  Returned {len(result)} tool(s)")
        for t in result:
            name = getattr(t, "name", None) or getattr(t, "function", {}).get("name", "?")
            print(f"    -> {name}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")

    # (3) Via toolkits
    print()
    print("=" * 60)
    print(f"TEST 3: tools.get(user_id='{test_user_id}', toolkits=['composio_search'])")
    print("=" * 60)
    try:
        result = client.tools.get(test_user_id, toolkits=["composio_search"])
        print(f"  Returned {len(result)} tool(s)")
        for t in result:
            name = getattr(t, "name", None) or getattr(t, "function", {}).get("name", "?")
            print(f"    -> {name}")
    except Exception as e:
        print(f"  ERROR: {type(e).__name__}: {e}")
