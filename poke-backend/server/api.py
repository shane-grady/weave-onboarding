from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import asyncio
import os

from .models import User
from .agent import ResearchAgent
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
composio_client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))
research_agent = ResearchAgent()


class ConnectionRequest(BaseModel):
    user_id: str
    auth_config_id: Optional[str] = None


class UserCreateRequest(BaseModel):
    connection_id: str
    name: Optional[str] = None


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


@app.post("/research/{user_id}")
async def research_user(user_id: str):
    """Trigger research on a connected user. Returns structured personal data."""
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark as in-progress
    research_results[user_id] = {"status": "processing"}

    try:
        result = await research_agent.research(user_id)
        research_results[user_id] = {"status": "completed", "data": result}
        return {"status": "completed", "data": result}
    except Exception as e:
        print(f"Research error: {e}")
        research_results[user_id] = {"status": "error", "data": None}
        raise HTTPException(status_code=500, detail="Research failed")


@app.get("/research/{user_id}/status")
async def get_research_status(user_id: str):
    """Poll for research completion."""
    return research_results.get(user_id, {"status": "not_started"})


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
