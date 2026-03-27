from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone


class User(BaseModel):
    connection_id: str
    name: Optional[str] = None


class Message(BaseModel):
    id: str
    user_id: str
    content: str
    response: Optional[str] = None
    status: str = "queued"  # queued | processing | completed | error
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
