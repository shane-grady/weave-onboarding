from composio import Composio


def get_stripe_tools(composio_client: Composio, user_id: str):
    return composio_client.tools.get(user_id, toolkits=["STRIPE"])


def get_google_tools(composio_client: Composio, user_id: str):
    return composio_client.tools.get(
        user_id,
        tools=[
            # Gmail profile & contacts (compact, structured data)
            "GMAIL_GET_PROFILE",
            "GMAIL_SEARCH_PEOPLE",
            "GMAIL_GET_CONTACTS",
            # Web search (multiple strategies)
            "COMPOSIO_SEARCH_SEARCH",
            "COMPOSIO_SEARCH_NEWS",
            "COMPOSIO_SEARCH_FETCH_URL_CONTENT",
            "COMPOSIO_SEARCH_EXA_ANSWER",
        ],
    )
