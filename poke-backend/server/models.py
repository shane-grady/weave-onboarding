from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    connection_id: str
    name: Optional[str] = None
