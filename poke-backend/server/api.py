from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import uuid
import os

from .models import User, Message
from .agent import WeaveAgent
from .connection import initiate_connection, get_connection_status
from composio import Composio

app = FastAPI(title="Weave Fabric Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

users: Dict[str, User] = {}
research_results: Dict[str, dict] = {}
messages: Dict[str, Message] = {}
composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
agent = WeaveAgent()


class ConnectionRequest(BaseModel):
    user_id: str
    auth_config_id: Optional[str] = None


class UserCreateRequest(BaseModel):
    connection_id: str
    name: Optional[str] = None


class MessageRequest(BaseModel):
    user_id: str
    content: str


@app.post("/users")
async def create_user(request: UserCreateRequest):
    user = User(connection_id=request.connection_id, name=request.name)
    users[user.connection_id] = user
    return {"user_id": user.connection_id}


@app.post("/connections/initiate")
async def initiate_user_connection(request: ConnectionRequest):
    try:
        connected_account = initiate_connection(
            user_id=request.user_id,
            composio_client=composio_client,
            auth_config_id=request.auth_config_id,
        )
        return {
            "connection_id": connected_account.id,
            "redirect_url": connected_account.redirect_url,
        }
    except Exception as e:
        print(f"Connection error: {e}")
        raise HTTPException(status_code=500, detail="Connection failed")


@app.get("/connections/{connection_id}/status")
async def check_connection_status(connection_id: str):
    try:
        status = get_connection_status(
            connected_account_id=connection_id,
            composio_client=composio_client,
        )
        return {"status": status.status, "connection_id": connection_id}
    except Exception as e:
        print(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail="Unable to check connection status")


async def _run_research(user_id: str):
    try:
        result = await agent.research(user_id)
        opening = await agent.generate_opening(result)
        research_results[user_id] = {
            "status": "completed",
            "data": result,
            "opening_message": opening,
        }
    except Exception as e:
        print(f"Research error: {e}")
        research_results[user_id] = {"status": "error", "data": None}


@app.post("/research/{user_id}")
async def research_user(user_id: str):
    """Trigger research on a connected user. Returns immediately."""
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    research_results[user_id] = {"status": "processing"}
    asyncio.create_task(_run_research(user_id))
    return {"status": "processing"}


@app.get("/research/{user_id}/status")
async def get_research_status(user_id: str):
    """Poll for research completion."""
    return research_results.get(user_id, {"status": "not_started"})


async def _process_message(message_id: str):
    msg = messages[message_id]
    msg.status = "processing"
    try:
        research = research_results.get(msg.user_id, {}).get("data", {})
        history = [
            {"content": m.content, "response": m.response}
            for m in messages.values()
            if m.user_id == msg.user_id and m.status == "completed" and m.id != message_id
        ]
        response = await agent.chat(msg.user_id, msg.content, research, history)
        msg.response = response
        msg.status = "completed"
    except Exception as e:
        print(f"Message processing error: {e}")
        msg.status = "error"


@app.post("/messages")
async def send_message(request: MessageRequest):
    """Send a chat message. Returns immediately with message ID."""
    message_id = str(uuid.uuid4())
    msg = Message(id=message_id, user_id=request.user_id, content=request.content)
    messages[message_id] = msg
    asyncio.create_task(_process_message(message_id))
    return {"message_id": message_id, "status": "queued"}


@app.get("/messages/{message_id}")
async def get_message(message_id: str):
    """Poll for message response."""
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return {
        "message_id": msg.id,
        "status": msg.status,
        "content": msg.content,
        "response": msg.response,
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
